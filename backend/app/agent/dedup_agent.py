import hashlib
import json
import re
import time
import unicodedata
import uuid
from collections.abc import Awaitable, Callable

from rapidfuzz import fuzz
from slugify import slugify
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agent.deduplication import (
    extract_distinctive_name_tokens,
    extract_name_tokens,
    merge_projects,
)
from app.agent.llm_extractor import LLMExtractor, parse_json_content
from app.data.departments import format_department, normalize_department
from app.models.dedup_decision import DedupDecision
from app.models.project import Project
from app.models.run import Run

StepLogger = Callable[[str, dict | None, int | None], Awaitable[None]]

FUZZY_AUTO_MERGE = 0.9
# Seuil bas pour élargir la bande LLM (score < AUTO_MERGE) : plus de paires ambiguës passent au modèle.
FUZZY_CANDIDATE_MIN = 0.45
# Même promoteur + même commune + tokens communs : fusion auto sans LLM.
COMPANY_CITY_AUTO_MERGE = 0.65
# Adresse : seuils plus bas car les libellés d'articles varient fortement (lieu-dit vs nom commercial).
ADDRESS_AUTO_MERGE = 0.88
ADDRESS_CANDIDATE_MIN = 0.55
COMPANY_SIMILARITY_MIN = 0.85
PEOPLE_NAME_SIMILARITY_MIN = 0.85

_SAME_PROJECT_PROMPT = """Tu compares deux fiches projet extraites d'articles différents.
S'agit-il du MÊME chantier physique (même site, même zone d'activité, même construction) ?

Chaque fiche contient tous les champs extraits (nom, ville, promoteur, adresse, surface, statut, secteur, contacts, pitch) ainsi que les articles sources (titre, URL, extrait).

PRIORITÉ — compare d'abord les adresses (address), la ville (city) et le département :
- Même adresse, même lieu-dit, même zone commerciale/industrielle ou adresse partiellement identique → same_project: true même si les noms diffèrent fortement
- Ex. "Valvert Croix-Blanche" et "Nouveau centre commercial XXL en Essonne" peuvent être le même chantier si l'adresse ou le lieu-dit (Croix-Blanche, route citée, zone d'activité) correspond
- Un nom peut être une marque ("Valvert") et l'autre un libellé générique ("nouveau centre commercial", "méga entrepôt") : l'adresse tranche

Réponds same_project: true si :
- Variantes du même nom (ex. "Valvert", "Valvert Croix-Blanche", "Central Park Valvert")
- Même site malgré des libellés différents (entrepôt / méga-entrepôt / centre de distribution)
- Adresses similaires ou partageant un lieu-dit / rue / zone, surtout dans la même commune ou le même département
- Les articles sources décrivent le même chantier malgré des titres ou noms différents
- Même promoteur, même commune et les extraits parlent du même lieu ou de la même opération

Réponds same_project: false si ce sont deux projets distincts, même dans la même ville ou avec le même promoteur, et que les adresses ne correspondent pas.

Réponds UNIQUEMENT un JSON valide: {"same_project": true|false, "reason": "..."}"""

DISTINCTIVE_TOKEN_MIN_LEN = 5
_ADDRESS_TOKEN_MIN_LEN = 4
_SOURCE_EXCERPT_MAX_LEN = 2000
_ADDRESS_STOPWORDS = {
    "activite",
    "artisanale",
    "avenue",
    "boulevard",
    "centre",
    "chemin",
    "commercial",
    "commerciale",
    "departement",
    "est",
    "france",
    "impasse",
    "industrielle",
    "lieu",
    "nord",
    "ouest",
    "parc",
    "place",
    "route",
    "rue",
    "saint",
    "sainte",
    "sud",
    "zone",
}


def _normalize_address(value: str) -> str:
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    for char in "-_,;:/()":
        text = text.replace(char, " ")
    return " ".join(text.split())


def _normalize_label(value: str) -> str:
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return text.lower().strip()


def company_similarity(company_a: str | None, company_b: str | None) -> float:
    if not company_a or not company_b:
        return 0.0
    return fuzz.token_set_ratio(_normalize_label(company_a), _normalize_label(company_b)) / 100


def has_people_overlap(people_a: list, people_b: list) -> bool:
    names_a = [
        _normalize_label(person.get("name", ""))
        for person in people_a
        if person.get("name")
    ]
    names_b = [
        _normalize_label(person.get("name", ""))
        for person in people_b
        if person.get("name")
    ]
    if not names_a or not names_b:
        return False
    for name_a in names_a:
        for name_b in names_b:
            if fuzz.token_set_ratio(name_a, name_b) / 100 >= PEOPLE_NAME_SIMILARITY_MIN:
                return True
    return False


def extract_address_tokens(address: str) -> list[str]:
    normalized = _normalize_address(address)
    tokens = re.findall(r"[a-z0-9]{3,}", normalized)
    return sorted({token for token in tokens if token not in _ADDRESS_STOPWORDS and len(token) >= _ADDRESS_TOKEN_MIN_LEN})


def address_similarity(address_a: str | None, address_b: str | None) -> float:
    if not address_a or not address_b:
        return 0.0
    tokens_a = " ".join(extract_address_tokens(address_a))
    tokens_b = " ".join(extract_address_tokens(address_b))
    if not tokens_a or not tokens_b:
        return 0.0
    return fuzz.token_sort_ratio(tokens_a, tokens_b) / 100


def has_address_overlap(address_a: str | None, address_b: str | None) -> bool:
    tokens_a = set(extract_address_tokens(address_a or ""))
    tokens_b = set(extract_address_tokens(address_b or ""))
    if not tokens_a or not tokens_b:
        return False
    shared = tokens_a & tokens_b
    if not shared:
        return False
    if tokens_a <= tokens_b or tokens_b <= tokens_a:
        return True
    if len(shared) >= 2:
        return True
    return any(len(token) >= DISTINCTIVE_TOKEN_MIN_LEN for token in shared)


def name_similarity(name_a: str, name_b: str) -> float:
    tokens_a = " ".join(extract_name_tokens(name_a))
    tokens_b = " ".join(extract_name_tokens(name_b))
    if not tokens_a or not tokens_b:
        return 0.0
    return fuzz.token_sort_ratio(tokens_a, tokens_b) / 100


def has_brand_overlap(name_a: str, name_b: str) -> bool:
    tokens_a = set(extract_distinctive_name_tokens(name_a))
    tokens_b = set(extract_distinctive_name_tokens(name_b))
    if not tokens_a or not tokens_b:
        return False

    shared = tokens_a & tokens_b
    if not shared:
        return False
    if tokens_a <= tokens_b or tokens_b <= tokens_a:
        return True
    if len(shared) >= 2:
        return True
    return any(len(token) >= DISTINCTIVE_TOKEN_MIN_LEN for token in shared)


def _same_city(city_a: str | None, city_b: str | None) -> bool:
    if not city_a or not city_b:
        return False
    return slugify(city_a) == slugify(city_b)


def _token_in_city_slug(token: str, city_slug: str) -> bool:
    if not city_slug:
        return False
    token_slug = slugify(token)
    if not token_slug:
        return False
    return token_slug in city_slug.split("-") or city_slug.startswith(token_slug)


def _same_company(project_a: Project, project_b: Project) -> bool:
    if company_similarity(project_a.company, project_b.company) >= COMPANY_SIMILARITY_MIN:
        return True
    for company, name in (
        (project_a.company, project_b.name),
        (project_b.company, project_a.name),
    ):
        if company and company_similarity(company, name) >= COMPANY_SIMILARITY_MIN:
            return True
    if project_a.company and project_b.company:
        return False
    if not has_brand_overlap(project_a.name, project_b.name):
        return False
    shared = set(extract_distinctive_name_tokens(project_a.name)) & set(
        extract_distinctive_name_tokens(project_b.name)
    )
    if not shared:
        return False
    city_slugs = {slugify(project_a.city or ""), slugify(project_b.city or "")}
    company_tokens = {
        token
        for token in shared
        if not any(_token_in_city_slug(token, city_slug) for city_slug in city_slugs)
    }
    return bool(company_tokens)


def _department_matches(
    project_department: str | None,
    target_label: str,
    *,
    country: str,
) -> bool:
    if not project_department:
        return False
    normalized = normalize_department(project_department, country)
    return normalized == target_label or project_department.strip() == target_label


def _should_auto_merge_company_city(
    kept: Project,
    absorbed: Project,
    *,
    name_score: float,
) -> bool:
    return (
        company_similarity(kept.company, absorbed.company) >= COMPANY_SIMILARITY_MIN
        and _same_city(kept.city, absorbed.city)
        and has_brand_overlap(kept.name, absorbed.name)
        and name_score >= COMPANY_CITY_AUTO_MERGE
    )


def _pair_match_score(
    name_score: float,
    address_score: float,
    *,
    brand_overlap: bool,
    address_overlap: bool,
) -> float:
    if address_score >= ADDRESS_AUTO_MERGE or (address_overlap and address_score >= ADDRESS_CANDIDATE_MIN):
        return max(name_score, address_score)
    if brand_overlap:
        return name_score
    return max(name_score, address_score)


def find_candidate_pairs(projects: list[Project]) -> list[tuple[Project, Project, float]]:
    pairs: list[tuple[Project, Project, float]] = []
    for index, project_a in enumerate(projects):
        for project_b in projects[index + 1 :]:
            name_score = name_similarity(project_a.name, project_b.name)
            brand_overlap = has_brand_overlap(project_a.name, project_b.name)
            address_score = address_similarity(project_a.address, project_b.address)
            address_overlap = has_address_overlap(project_a.address, project_b.address)
            company_score = company_similarity(project_a.company, project_b.company)
            people_overlap = has_people_overlap(
                project_a.people or [], project_b.people or []
            )

            name_match = name_score >= FUZZY_CANDIDATE_MIN or brand_overlap
            address_match = (
                address_score >= ADDRESS_CANDIDATE_MIN
                or address_overlap
                or address_score >= ADDRESS_AUTO_MERGE
            )
            company_match = company_score >= COMPANY_SIMILARITY_MIN
            people_match = people_overlap

            if not name_match and not address_match and not company_match and not people_match:
                continue

            # Candidature par nom : même commune ou même entreprise, sauf adresse ou contact.
            if (
                name_match
                and not address_match
                and not people_match
                and not (
                    _same_city(project_a.city, project_b.city)
                    or _same_company(project_a, project_b)
                )
            ):
                continue

            pair_score = _pair_match_score(
                name_score,
                address_score,
                brand_overlap=brand_overlap,
                address_overlap=address_overlap,
            )
            pairs.append((project_a, project_b, pair_score))
    return pairs


def _source_payload(source) -> dict:
    excerpt = source.raw_excerpt
    if excerpt and len(excerpt) > _SOURCE_EXCERPT_MAX_LEN:
        excerpt = excerpt[:_SOURCE_EXCERPT_MAX_LEN]
    return {
        "title": source.title,
        "url": source.url,
        "published_at": source.published_at.isoformat() if source.published_at else None,
        "excerpt": excerpt,
    }


def _project_payload(project: Project) -> dict:
    return {
        "name": project.name,
        "city": project.city,
        "company": project.company,
        "address": project.address,
        "department": project.department,
        "surface_m2": float(project.surface_m2) if project.surface_m2 is not None else None,
        "delivery_date": project.delivery_date,
        "status": project.status,
        "sector": project.sector,
        "people": project.people or [],
        "lead_pitch": project.lead_pitch,
        "sources": [_source_payload(source) for source in project.sources],
    }


async def ask_llm_same_project(
    llm: LLMExtractor,
    project_a: Project,
    project_b: Project,
    step_logger: StepLogger | None = None,
) -> tuple[bool, str]:
    user_content = (
        f"Fiche A: {json.dumps(_project_payload(project_a), ensure_ascii=False)}\n"
        f"Fiche B: {json.dumps(_project_payload(project_b), ensure_ascii=False)}"
    )
    import httpx

    from app.config import settings

    if step_logger:
        await step_logger(
            "llm_dedup_start",
            {"project_a": project_a.name, "project_b": project_b.name},
        )
    started = time.monotonic()
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://ai-gateway.vercel.sh/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {llm.api_key or settings.ai_gateway_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": llm.model,
                "messages": [
                    {"role": "system", "content": _SAME_PROJECT_PROMPT},
                    {"role": "user", "content": user_content},
                ],
            },
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        data = parse_json_content(content)
        same_project = bool(data.get("same_project"))
        reason = str(data.get("reason") or "").strip()
    if step_logger:
        await step_logger(
            "llm_dedup_done",
            {
                "project_a": project_a.name,
                "project_b": project_b.name,
                "same_project": same_project,
                "reason": reason,
            },
            duration_ms=int((time.monotonic() - started) * 1000),
        )
    return same_project, reason


def _auto_merge_reason(
    kept: Project,
    absorbed: Project,
    *,
    score: float,
    name_score: float,
    address_score: float,
) -> str:
    if address_score >= ADDRESS_AUTO_MERGE:
        return f"Adresses très similaires (score adresse {address_score:.0%})"
    if _should_auto_merge_company_city(kept, absorbed, name_score=name_score):
        return "Même promoteur, même commune et noms proches"
    return f"Similarité des noms ≥ {FUZZY_AUTO_MERGE:.0%} (score {score:.0%})"


_FINGERPRINT_FIELDS = (
    "name",
    "company",
    "siren",
    "city",
    "address",
    "department",
    "status",
    "sector",
)


def _project_fingerprint(project: Project) -> str:
    values = [str(getattr(project, field) or "") for field in _FINGERPRINT_FIELDS]
    values.append(str(project.surface_m2 or ""))
    values.append(str(project.delivery_date or ""))
    return "|".join(values)


def _pair_key(project_a: Project, project_b: Project) -> tuple[uuid.UUID, uuid.UUID]:
    if str(project_a.id) <= str(project_b.id):
        return project_a.id, project_b.id
    return project_b.id, project_a.id


def pair_fingerprint(project_a: Project, project_b: Project) -> str:
    first, second = sorted(
        (_project_fingerprint(project_a), _project_fingerprint(project_b))
    )
    return hashlib.sha256(f"{first}||{second}".encode()).hexdigest()


def get_cached_verdict(
    session: Session, project_a: Project, project_b: Project
) -> tuple[bool, str] | None:
    a_id, b_id = _pair_key(project_a, project_b)
    decision = (
        session.query(DedupDecision)
        .filter(
            DedupDecision.project_a_id == a_id,
            DedupDecision.project_b_id == b_id,
        )
        .first()
    )
    if decision is None or decision.pair_fingerprint != pair_fingerprint(project_a, project_b):
        return None
    return decision.same_project, decision.reason or ""


def store_verdict(
    session: Session,
    project_a: Project,
    project_b: Project,
    *,
    same_project: bool,
    reason: str,
    run_id: uuid.UUID | None,
) -> None:
    a_id, b_id = _pair_key(project_a, project_b)
    decision = (
        session.query(DedupDecision)
        .filter(
            DedupDecision.project_a_id == a_id,
            DedupDecision.project_b_id == b_id,
        )
        .first()
    )
    if decision is None:
        decision = DedupDecision(
            project_a_id=a_id,
            project_b_id=b_id,
            same_project=same_project,
            reason=reason or None,
            pair_fingerprint=pair_fingerprint(project_a, project_b),
            run_id=run_id,
        )
        try:
            with session.begin_nested():
                session.add(decision)
                session.flush()
        except IntegrityError:
            # Course avec une autre passe de dédup : la ligne existe déjà, on la met à jour.
            decision = (
                session.query(DedupDecision)
                .filter(
                    DedupDecision.project_a_id == a_id,
                    DedupDecision.project_b_id == b_id,
                )
                .one()
            )
            decision.same_project = same_project
            decision.reason = reason or None
            decision.pair_fingerprint = pair_fingerprint(project_a, project_b)
            decision.run_id = run_id
    else:
        decision.same_project = same_project
        decision.reason = reason or None
        decision.pair_fingerprint = pair_fingerprint(project_a, project_b)
        decision.run_id = run_id
    session.flush()


def _pick_survivor(project_a: Project, project_b: Project) -> tuple[Project, Project]:
    if project_a.first_seen_at and project_b.first_seen_at:
        if project_a.first_seen_at <= project_b.first_seen_at:
            return project_a, project_b
        return project_b, project_a
    if len(project_a.sources) >= len(project_b.sources):
        return project_a, project_b
    return project_b, project_a


async def run_dedup_pass(
    session: Session,
    run: Run,
    departments: list[str],
    country: str = "FR",
    llm: LLMExtractor | None = None,
    step_logger: StepLogger | None = None,
) -> list[dict]:
    llm = llm or LLMExtractor()
    merged_events: list[dict] = []

    for department_code in departments:
        department_label = format_department(department_code, country) or department_code

        while True:
            department_prefix = f"{department_code.strip().upper()}%"
            projects = [
                project
                for project in session.query(Project)
                .filter(
                    Project.merged_into_id.is_(None),
                    Project.department.isnot(None),
                    func.coalesce(Project.country, country) == country,
                    Project.department.like(department_prefix),
                )
                .all()
                if _department_matches(project.department, department_label, country=country)
            ]
            merged_in_pass = False
            for project_a, project_b, score in find_candidate_pairs(projects):
                kept, absorbed = _pick_survivor(project_a, project_b)
                if absorbed.merged_into_id is not None or kept.merged_into_id is not None:
                    continue

                name_score = name_similarity(kept.name, absorbed.name)
                address_score = address_similarity(kept.address, absorbed.address)
                address_overlap = has_address_overlap(kept.address, absorbed.address)
                company_score = company_similarity(kept.company, absorbed.company)
                people_overlap = has_people_overlap(
                    kept.people or [], absorbed.people or []
                )

                should_merge = (
                    score >= FUZZY_AUTO_MERGE
                    or address_score >= ADDRESS_AUTO_MERGE
                    or _should_auto_merge_company_city(
                        kept, absorbed, name_score=name_score
                    )
                )
                method = "fuzzy"
                merge_reason = ""
                if should_merge:
                    merge_reason = _auto_merge_reason(
                        kept,
                        absorbed,
                        score=score,
                        name_score=name_score,
                        address_score=address_score,
                    )
                if not should_merge and (
                    name_score >= FUZZY_CANDIDATE_MIN
                    or has_brand_overlap(kept.name, absorbed.name)
                    or address_score >= ADDRESS_CANDIDATE_MIN
                    or address_overlap
                    or company_score >= COMPANY_SIMILARITY_MIN
                    or people_overlap
                ):
                    cached = get_cached_verdict(session, kept, absorbed)
                    if cached is not None:
                        should_merge, merge_reason = cached
                        method = "llm_cached"
                    else:
                        should_merge, merge_reason = await ask_llm_same_project(
                            llm, kept, absorbed, step_logger=step_logger
                        )
                        store_verdict(
                            session,
                            kept,
                            absorbed,
                            same_project=should_merge,
                            reason=merge_reason,
                            run_id=run.id,
                        )
                        method = "llm"

                if not should_merge:
                    continue

                merge_projects(
                    session,
                    kept,
                    absorbed,
                    run_id=run.id,
                    method=method,
                    score=score,
                    reason=merge_reason,
                )
                run.projects_merged += 1
                session.commit()
                merged_events.append(
                    {
                        "kept_id": str(kept.id),
                        "kept_name": kept.name,
                        "absorbed_id": str(absorbed.id),
                        "absorbed_name": absorbed.name,
                        "method": method,
                        "score": score,
                    }
                )
                merged_in_pass = True
                break

            if not merged_in_pass:
                break

    return merged_events
