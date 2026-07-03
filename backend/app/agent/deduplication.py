import re
import unicodedata
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from slugify import slugify
from sqlalchemy.orm import Session

from app.agent.schemas import CompanyResolution, ProjectExtraction
from app.models.project import Project
from app.models.project_merge import ProjectMerge
from app.models.project_update import ProjectUpdate
from app.models.source import Source

STATUS_PRIORITY = {"conception": 0, "travaux": 1, "livraison": 2}

TRACKED_FIELDS = (
    "name",
    "company",
    "siren",
    "company_legal_name",
    "naf_code",
    "surface_m2",
    "delivery_date",
    "city",
    "address",
    "department",
    "country",
    "status",
    "sector",
)

_PREFIXES = sorted(
    [
        "new amazon logistics center",
        "amazon distribution center",
        "distribution center",
        "logistics center",
        "mega-entrepot",
        "entrepot frigorifique",
        "plateforme logistique",
        "entrepot",
        "extension of",
        "expansion of",
        "germany's largest",
        "largest",
    ],
    key=len,
    reverse=True,
)
_STOPWORDS = {"pour", "avec", "dans", "chez", "site", "projet", "nouveau", "nouvelle"}
_TOKEN_ALIASES = {
    "center": "centre",
    "centre": "centre",
    "logistics": "distribution",
    "distribution": "distribution",
    "extension": "expansion",
    "expansion": "expansion",
    "warehouse": "entrepot",
    "entrepot": "entrepot",
    "galeries": "galerie",
    "galerie": "galerie",
    "nouvelles": "galerie",
    "lafayette": "galerie",
}
_GENERIC_TOKENS = {
    "branch",
    "france",
    "germany",
    "largest",
    "new",
}
# Tokens descriptifs d'infrastructure — exclus de la match_key, conservés pour le fuzzy.
_MATCH_KEY_DROP = {
    "centre",
    "distribution",
    "entrepot",
    "mega",
    "logistics",
    "warehouse",
    "expansion",
    "extension",
    *_GENERIC_TOKENS,
}
# Mots génériques exclus du brand_overlap (match_key + secteur bâtiment/logistique).
_BRAND_OVERLAP_DROP = _MATCH_KEY_DROP | {
    "building",
    "competence",
    "construction",
    "factory",
    "industrial",
    "park",
}


def _normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return text.lower().strip()


def _canonical_token(token: str) -> str:
    return _TOKEN_ALIASES.get(token, token)


def extract_name_tokens(name: str) -> list[str]:
    normalized = _normalize_text(name)
    stripped = normalized
    matched_prefix = ""
    for prefix in _PREFIXES:
        if stripped.startswith(prefix):
            matched_prefix = prefix
            stripped = stripped[len(prefix) :].strip(" -/")
            break
    tokens = _tokens_from(stripped)
    if matched_prefix:
        tokens |= _tokens_from(matched_prefix)
    return sorted(tokens)


def extract_distinctive_name_tokens(name: str) -> list[str]:
    return [token for token in extract_name_tokens(name) if token not in _BRAND_OVERLAP_DROP]


def _tokens_from(text: str) -> set[str]:
    raw_tokens = re.findall(r"[a-z0-9]{4,}", text)
    return {
        _canonical_token(token)
        for token in raw_tokens
        if token not in _STOPWORDS and token not in _GENERIC_TOKENS
    }


def make_match_key(name: str, city: str | None, company: str | None = None) -> str:
    tokens = [token for token in extract_name_tokens(name or "unknown") if token not in _MATCH_KEY_DROP]
    token_part = "|".join(tokens) if tokens else "unknown"
    city_part = slugify(city or "unknown")
    return f"{token_part}|{city_part}"


def _normalize_delivery_date(value: date | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    return text or None


def merge_people(existing: list[dict], new_people: list[dict]) -> list[dict]:
    by_name = {p.get("name", "").lower(): p for p in existing if p.get("name")}
    for person in new_people:
        name = person.get("name", "")
        if not name:
            continue
        key = name.lower()
        if key not in by_name:
            by_name[key] = person
    return list(by_name.values())


def _pick_status(current: str | None, new: str | None) -> str | None:
    if new is None:
        return current
    if current is None:
        return new
    return new if STATUS_PRIORITY.get(new, -1) > STATUS_PRIORITY.get(current, -1) else current


def _fill_field(current, new):
    return current if current not in (None, "", []) else new


def _serialize_field_value(field: str, value):
    if value is None:
        return None
    if field == "surface_m2":
        return int(value)
    if field == "delivery_date":
        return value.isoformat() if hasattr(value, "isoformat") else str(value)
    return value


def _project_field_snapshot(project: Project) -> dict:
    return {field: _serialize_field_value(field, getattr(project, field)) for field in TRACKED_FIELDS}


def _format_person(person: dict) -> str:
    name = person.get("name", "")
    role = person.get("role")
    return f"{name} ({role})" if role else name


def compute_field_changes(before: dict, after: dict, *, people_before: list, people_after: list) -> list[dict]:
    changes: list[dict] = []
    for field in TRACKED_FIELDS:
        old = before.get(field)
        new = after.get(field)
        if old != new and new not in (None, ""):
            changes.append({"field": field, "old": old, "new": new})

    old_names = {person.get("name", "").lower() for person in people_before if person.get("name")}
    added_people = [
        person for person in people_after if person.get("name", "").lower() not in old_names
    ]
    if added_people:
        changes.append(
            {
                "field": "people",
                "old": None,
                "new": ", ".join(_format_person(person) for person in added_people),
            }
        )
    return changes


def merge_projects(
    session: Session,
    kept: Project,
    absorbed: Project,
    *,
    run_id: uuid.UUID | None,
    method: str,
    score: float | None = None,
    reason: str | None = None,
) -> ProjectMerge:
    before_fields = _project_field_snapshot(kept)
    people_before = list(kept.people or [])
    snapshot = {
        "kept": {"name": kept.name, "company": kept.company, "city": kept.city},
        "absorbed": {"name": absorbed.name, "company": absorbed.company, "city": absorbed.city},
        "sources_transferred": [
            {"url": source.url, "title": source.title} for source in list(absorbed.sources)
        ],
    }

    for source in list(absorbed.sources):
        source.project_id = kept.id

    if len(absorbed.name) > len(kept.name):
        kept.name = absorbed.name
    kept.company = _fill_field(kept.company, absorbed.company)
    kept.siren = _fill_field(kept.siren, absorbed.siren)
    kept.company_legal_name = _fill_field(kept.company_legal_name, absorbed.company_legal_name)
    kept.naf_code = _fill_field(kept.naf_code, absorbed.naf_code)
    if kept.surface_m2 is None and absorbed.surface_m2 is not None:
        kept.surface_m2 = absorbed.surface_m2
    if kept.delivery_date is None:
        kept.delivery_date = absorbed.delivery_date
    kept.city = _fill_field(kept.city, absorbed.city)
    kept.address = _fill_field(kept.address, absorbed.address)
    kept.department = _fill_field(kept.department, absorbed.department)
    kept.country = _fill_field(kept.country, absorbed.country)
    kept.status = _pick_status(kept.status, absorbed.status)
    kept.sector = _fill_field(kept.sector, absorbed.sector)
    kept.people = merge_people(kept.people or [], absorbed.people or [])
    kept.lead_pitch = _fill_field(kept.lead_pitch, absorbed.lead_pitch)
    kept.last_updated_at = datetime.now(timezone.utc)

    after_fields = _project_field_snapshot(kept)
    snapshot["changes"] = compute_field_changes(
        before_fields,
        after_fields,
        people_before=people_before,
        people_after=list(kept.people or []),
    )
    if reason and reason.strip():
        snapshot["reason"] = reason.strip()

    absorbed.merged_into_id = kept.id

    merge = ProjectMerge(
        run_id=run_id,
        kept_project_id=kept.id,
        absorbed_project_id=absorbed.id,
        method=method,
        score=score,
        snapshot=snapshot,
    )
    session.add(merge)
    session.flush()
    return merge


def _find_project_by_match_key(session: Session, match_key: str) -> Project | None:
    project = session.query(Project).filter(Project.match_key == match_key).first()
    if not project:
        return None
    while project.merged_into_id is not None:
        parent = session.get(Project, project.merged_into_id)
        if parent is None:
            break
        project = parent
    return project


def upsert_project(
    session: Session,
    extraction: ProjectExtraction,
    *,
    url: str,
    title: str | None,
    raw_excerpt: str | None,
    run_id: uuid.UUID,
    country: str = "FR",
    company_resolution: CompanyResolution | None = None,
    published_at: date | None = None,
) -> tuple[Project, bool]:
    existing_source = session.query(Source).filter(Source.url == url).first()
    if existing_source:
        if published_at and existing_source.published_at is None:
            existing_source.published_at = published_at
            extracted_data = dict(existing_source.extracted_data or {})
            extracted_data["published_at"] = published_at.isoformat()
            existing_source.extracted_data = extracted_data
        return existing_source.project, False

    match_key = make_match_key(extraction.name, extraction.city, extraction.company)
    project = _find_project_by_match_key(session, match_key)
    is_new = project is None

    people_data = [p.model_dump() for p in extraction.people]

    if is_new:
        project = Project(
            name=extraction.name,
            company=extraction.company,
            surface_m2=Decimal(str(extraction.surface_m2)) if extraction.surface_m2 else None,
            delivery_date=_normalize_delivery_date(extraction.delivery_date),
            city=extraction.city,
            address=extraction.address,
            department=extraction.department,
            country=country,
            status=extraction.status,
            sector=extraction.sector,
            people=people_data,
            lead_pitch=extraction.lead_pitch,
            match_key=match_key,
        )
        if company_resolution and company_resolution.matched:
            project.siren = company_resolution.siren
            project.company_legal_name = company_resolution.company_legal_name
            project.naf_code = company_resolution.naf_code
        session.add(project)
        session.flush()
        changes: list[dict] = []
    else:
        before_fields = _project_field_snapshot(project)
        people_before = list(project.people or [])
        project.name = _fill_field(project.name, extraction.name)
        project.company = _fill_field(project.company, extraction.company)
        if project.surface_m2 is None and extraction.surface_m2:
            project.surface_m2 = Decimal(str(extraction.surface_m2))
        if project.delivery_date is None:
            project.delivery_date = _normalize_delivery_date(extraction.delivery_date)
        project.city = _fill_field(project.city, extraction.city)
        project.address = _fill_field(project.address, extraction.address)
        project.department = _fill_field(project.department, extraction.department)
        project.country = country
        project.status = _pick_status(project.status, extraction.status)
        project.sector = _fill_field(project.sector, extraction.sector)
        project.people = merge_people(project.people or [], people_data)
        project.lead_pitch = _fill_field(project.lead_pitch, extraction.lead_pitch)
        if company_resolution and company_resolution.matched:
            if not project.siren:
                project.siren = company_resolution.siren
            project.company_legal_name = _fill_field(
                project.company_legal_name, company_resolution.company_legal_name
            )
            project.naf_code = _fill_field(project.naf_code, company_resolution.naf_code)
        project.last_updated_at = datetime.now(timezone.utc)
        after_fields = _project_field_snapshot(project)
        changes = compute_field_changes(
            before_fields,
            after_fields,
            people_before=people_before,
            people_after=list(project.people or []),
        )

    extracted_data = extraction.model_dump(mode="json")
    if published_at:
        extracted_data["published_at"] = published_at.isoformat()

    source = Source(
        project_id=project.id,
        url=url,
        title=title,
        published_at=published_at,
        raw_excerpt=raw_excerpt,
        extracted_data=extracted_data,
        run_id=run_id,
    )
    session.add(source)
    session.flush()

    if not is_new and changes:
        session.add(
            ProjectUpdate(
                run_id=run_id,
                project_id=project.id,
                source_id=source.id,
                changes=changes,
            )
        )
        session.flush()

    return project, is_new
