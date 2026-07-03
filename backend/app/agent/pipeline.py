import asyncio
import time
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.agent.blocked_domains import exa_exclude_domains, is_blocked_url
from app.agent.company_resolver import CompanyResolver
from app.agent.deduplication import upsert_project
from app.agent.dedup_agent import run_dedup_pass
from app.agent.entreprise_client import EntrepriseClient, extract_dept_code
from app.agent.schemas import CompanyResolution, ProjectExtraction
from app.data.departments import department_name, ensure_department, format_department, normalize_department
from app.data.search_anchors_loader import anchor_segment_for_cities
from app.agent.exa_client import ExaClient, parse_exa_published_date, published_dates_by_url
from app.agent.published_date_presets import resolve_published_date_range
from app.agent.llm_extractor import LLMExtractor
from app.agent.queries import SECTOR_QUERIES_BY_COUNTRY
from app.agent.url_prefilter import UrlPrefilter
from app.api.config import get_or_create_config
from app.config import settings
from app.models.run import Run
from app.models.run_step import RunStep
from app.agent.known_urls import load_known_urls, mark_url_seen

_run_events: dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)

EXA_NUM_RESULTS = 25
MAX_FETCH_PER_SEARCH = 10

_STEP_MESSAGES = {
    "run_started": "Run démarré",
    "searching": "Recherche articles — {sector} (dept. {department})",
    "exa_search_start": "Exa — lancement recherche ({sector}, dept. {department})",
    "exa_search_done": "Exa — {result_count} résultat(s) en {duration_ms} ms",
    "prefilter_start": "Préfiltre LLM — {candidate_count} candidat(s)",
    "prefilter_done": "Préfiltre LLM — {kept_count} retenu(s), {rejected_count} rejeté(s) en {duration_ms} ms",
    "prefilter_failed": "Préfiltre LLM indisponible — fallback top {fallback_count}",
    "exa_fetch_start": "Exa — récupération de {url_count} URL(s)",
    "exa_fetch_done": "Exa — {fetched_count} article(s) récupéré(s) en {duration_ms} ms",
    "article_skipped": "Article ignoré ({reason}) : {title}",
    "extracting": "Analyse article : {title}",
    "llm_extract_start": "LLM — extraction démarrée ({model})",
    "llm_extract_done": "LLM — extraction terminée en {duration_ms} ms (pertinent={is_relevant})",
    "article_not_relevant": "Article non pertinent : {title}",
    "company_searching": "Recherche SIREN pour {company}",
    "api_entreprise_search_start": "API gouv — recherche entreprise « {company} »",
    "api_entreprise_search_done": "API gouv — {candidate_count} candidat(s) en {duration_ms} ms",
    "llm_company_resolve_start": "LLM — résolution SIREN ({candidate_count} candidat(s))",
    "llm_company_resolve_done": "LLM — résolution SIREN en {duration_ms} ms (matched={matched})",
    "company_resolved": "SIREN identifié : {siren} ({company_legal_name})",
    "company_skipped": "SIREN non identifié : {reason}",
    "project_found": "Projet traité : {name}",
    "deduplicating": "Consolidation des doublons…",
    "llm_dedup_start": "LLM — comparaison doublons : {project_a} vs {project_b}",
    "llm_dedup_done": "LLM — comparaison doublons en {duration_ms} ms (same={same_project}){reason_suffix}",
    "project_merged": "Fusion : {absorbed_name} → {kept_name}",
    "run_completed": "Run terminé",
    "run_failed": "Run échoué : {error}",
}

StepLogger = Callable[[str, dict | None, int | None], Awaitable[None]]


def get_run_queue(run_id: str) -> asyncio.Queue:
    return _run_events[run_id]


async def emit_event(run_id: uuid.UUID, event: str, data: dict | None = None):
    queue = get_run_queue(str(run_id))
    await queue.put({"event": event, "data": data or {}})


def step_message(event: str, data: dict | None) -> str:
    data = dict(data or {})
    if event == "llm_dedup_done":
        reason = str(data.get("reason") or "").strip()
        data["reason_suffix"] = f" — {reason}" if reason else ""
    template = _STEP_MESSAGES.get(event, event)
    try:
        return template.format(**data)
    except KeyError:
        return template


def _exa_search_results_payload(results: list[dict]) -> list[dict]:
    items: list[dict] = []
    for result in results:
        url = result.get("url")
        if not url:
            continue
        item: dict = {"url": url, "title": result.get("title") or url}
        if result.get("score") is not None:
            item["score"] = result["score"]
        if result.get("publishedDate"):
            item["published_at"] = result["publishedDate"]
        highlights = result.get("highlights") or []
        if highlights:
            snippet = highlights[0]
            if isinstance(snippet, str):
                item["snippet"] = snippet[:300]
        items.append(item)
    return items


def _exa_fetch_articles_payload(items: list[dict]) -> list[dict]:
    articles: list[dict] = []
    for item in items:
        url = item.get("url")
        if not url:
            continue
        text = item.get("text") or ""
        article: dict = {
            "url": url,
            "title": item.get("title") or url,
            "text_length": len(text.strip()),
        }
        published_at = parse_exa_published_date(item.get("publishedDate"))
        if published_at:
            article["published_at"] = published_at.isoformat()
        articles.append(article)
    return articles


async def _emit_article_skipped(
    session: Session,
    run_id: uuid.UUID,
    *,
    url: str,
    title: str,
    reason: str,
) -> None:
    await log_and_emit(
        session,
        run_id,
        "article_skipped",
        {"url": url, "title": title, "reason": reason},
    )


def _offset_ms(session: Session, run_id: uuid.UUID) -> int:
    run = session.get(Run, run_id)
    if not run or not run.started_at:
        return 0
    started = run.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - started
    return max(0, int(delta.total_seconds() * 1000))


async def log_and_emit(
    session: Session,
    run_id: uuid.UUID,
    event: str,
    data: dict | None = None,
    duration_ms: int | None = None,
):
    payload = dict(data or {})
    payload["offset_ms"] = _offset_ms(session, run_id)
    if duration_ms is not None:
        payload["duration_ms"] = duration_ms
    message = step_message(event, payload)
    session.add(
        RunStep(
            run_id=run_id,
            step_type=event,
            message=message,
            data=payload,
        )
    )
    session.commit()
    await emit_event(run_id, event, payload)


def make_step_logger(session: Session, run_id: uuid.UUID) -> StepLogger:
    async def log(event: str, data: dict | None = None, duration_ms: int | None = None) -> None:
        await log_and_emit(session, run_id, event, data, duration_ms=duration_ms)

    return log


async def enrich_company(
    extraction: ProjectExtraction,
    *,
    article_text: str,
    country: str,
    entreprise: EntrepriseClient | None = None,
    resolver: CompanyResolver | None = None,
    step_logger: StepLogger | None = None,
) -> CompanyResolution:
    if country != "FR" or not extraction.company:
        return CompanyResolution(matched=False, reason="Pas d'entreprise ou pays non FR")

    entreprise = entreprise or EntrepriseClient()
    resolver = resolver or CompanyResolver()
    dept_code = extract_dept_code(extraction.department)

    if step_logger:
        await step_logger(
            "api_entreprise_search_start",
            {"company": extraction.company, "department": dept_code},
        )
    api_started = time.monotonic()
    candidates = await entreprise.search(
        extraction.company,
        departement=dept_code,
    )
    if step_logger:
        await step_logger(
            "api_entreprise_search_done",
            {"company": extraction.company, "candidate_count": len(candidates)},
            duration_ms=int((time.monotonic() - api_started) * 1000),
        )

    return await resolver.resolve(
        company_name=extraction.company,
        article_context=article_text,
        candidates=candidates,
        city=extraction.city,
        step_logger=step_logger,
    )


async def run_pipeline(session: Session, run_id: uuid.UUID | None = None) -> Run:
    config = get_or_create_config(session)

    if run_id:
        run = session.get(Run, run_id)
        if run and run.started_at is None:
            run.started_at = datetime.now(timezone.utc)
            session.commit()
    else:
        in_progress = session.query(Run).filter(Run.status == "in_progress").first()
        if in_progress:
            raise RuntimeError("A run is already in progress")

        run = Run(
            status="in_progress",
            started_at=datetime.now(timezone.utc),
            geographical_granularity=config.geographical_granularity or "large",
            exa_search_type=config.exa_search_type or "auto",
            exa_category=config.exa_category or "news",
        )
        session.add(run)
        session.commit()
        session.refresh(run)

    run_id = run.id
    test_single = run.mode == "test_single"
    step_logger = make_step_logger(session, run_id)
    await log_and_emit(
        session,
        run_id,
        "run_started",
        {
            "run_id": str(run_id),
            "mode": run.mode,
            "geographical_granularity": run.geographical_granularity,
            "exa_search_type": run.exa_search_type,
            "exa_category": run.exa_category,
        },
    )

    exa = ExaClient(settings.exa_api_key)
    llm = LLMExtractor()
    prefilter = UrlPrefilter()

    known_urls = load_known_urls(session)

    try:
        country = config.country or "FR"
        sector_queries = SECTOR_QUERIES_BY_COUNTRY.get(country, SECTOR_QUERIES_BY_COUNTRY["FR"])

        departments = config.departments[:1] if test_single else config.departments
        sectors = config.sectors[:1] if test_single else config.sectors

        for department in departments:
            for sector in sectors:
                query_template = sector_queries.get(sector)
                if not query_template:
                    continue

                dept_label = format_department(department, country) or department
                dept_name = department_name(department, country) or department
                region_cities_map = config.region_cities or {}
                if (config.geographical_granularity or "large") == "city_focus":
                    selected_cities = region_cities_map.get(department) or []
                else:
                    selected_cities = []
                anchor_segment = anchor_segment_for_cities(selected_cities, country)
                query = query_template.format(
                    dept=department,
                    dept_code=department,
                    dept_label=dept_label,
                    dept_name=dept_name,
                    anchor_segment=anchor_segment,
                )
                await log_and_emit(
                    session,
                    run_id,
                    "searching",
                    {"department": department, "sector": sector, "query": query},
                )

                try:
                    await step_logger(
                        "exa_search_start",
                        {"department": department, "sector": sector, "query": query},
                    )
                    search_started = time.monotonic()
                    effective_start, effective_end = resolve_published_date_range(
                        config.exa_published_date_preset,
                        config.exa_start_published_date,
                        config.exa_end_published_date,
                    )
                    search_results = await exa.search(
                        query,
                        num_results=EXA_NUM_RESULTS,
                        search_type=config.exa_search_type,
                        category=config.exa_category or None,
                        start_published_date=(
                            effective_start.isoformat() if effective_start else None
                        ),
                        end_published_date=(
                            effective_end.isoformat() if effective_end else None
                        ),
                        exclude_domains=exa_exclude_domains(config.exa_category or None),
                    )
                    await step_logger(
                        "exa_search_done",
                        {
                            "department": department,
                            "sector": sector,
                            "query": query,
                            "result_count": len(search_results),
                            "results": _exa_search_results_payload(search_results),
                        },
                        duration_ms=int((time.monotonic() - search_started) * 1000),
                    )
                except Exception:
                    continue

                new_urls = [
                    r["url"]
                    for r in search_results
                    if r.get("url")
                    and r["url"] not in known_urls
                    and not is_blocked_url(r["url"])
                ]

                search_by_url = {r["url"]: r for r in search_results if r.get("url")}
                for url, result in search_by_url.items():
                    if url in new_urls:
                        continue
                    if url in known_urls:
                        reason = "known"
                    elif is_blocked_url(url):
                        reason = "blocked"
                    else:
                        continue
                    await _emit_article_skipped(
                        session,
                        run_id,
                        url=url,
                        title=result.get("title") or url,
                        reason=reason,
                    )

                if not new_urls:
                    continue

                candidates = []
                for url in new_urls:
                    result = search_by_url.get(url) or {}
                    highlights = result.get("highlights") or []
                    snippet = highlights[0] if highlights and isinstance(highlights[0], str) else ""
                    candidates.append(
                        {
                            "url": url,
                            "title": result.get("title") or url,
                            "snippet": snippet,
                            "published_at": result.get("publishedDate"),
                            "score": result.get("score"),
                        }
                    )

                try:
                    decisions = await prefilter.select(candidates, step_logger=step_logger)
                except Exception as exc:
                    decisions = None  # fallback : tout garder, ordre Exa
                    await step_logger(
                        "prefilter_failed",
                        {
                            "fallback_count": min(len(new_urls), MAX_FETCH_PER_SEARCH),
                            "error": str(exc),
                        },
                    )

                if decisions is None:
                    kept_urls = new_urls[:MAX_FETCH_PER_SEARCH]
                else:
                    kept, rejected = [], []
                    for candidate in candidates:
                        fetch_flag, _reason = decisions.get(candidate["url"], (True, ""))
                        (kept if fetch_flag else rejected).append(candidate)
                    for candidate in rejected:
                        await _emit_article_skipped(
                            session,
                            run_id,
                            url=candidate["url"],
                            title=candidate["title"],
                            reason="prefiltered",
                        )
                    kept.sort(key=lambda c: c.get("score") or 0.0, reverse=True)
                    kept_urls = [c["url"] for c in kept[:MAX_FETCH_PER_SEARCH]]

                if not kept_urls:
                    continue

                published_by_url = published_dates_by_url(search_results)

                try:
                    await step_logger("exa_fetch_start", {"url_count": len(kept_urls)})
                    fetch_started = time.monotonic()
                    fetched = await exa.fetch(kept_urls)
                    published_by_url.update(published_dates_by_url(fetched))
                    await step_logger(
                        "exa_fetch_done",
                        {
                            "fetched_count": len(fetched),
                            "articles": _exa_fetch_articles_payload(fetched),
                        },
                        duration_ms=int((time.monotonic() - fetch_started) * 1000),
                    )
                except Exception:
                    continue

                found_relevant = False
                for item in fetched:
                    url = item.get("url")
                    if not url or url in known_urls or is_blocked_url(url):
                        continue

                    text = item.get("text") or ""
                    title = item.get("title") or ""
                    if len(text.strip()) < 100:
                        await _emit_article_skipped(
                            session, run_id, url=url, title=title, reason="short_text"
                        )
                        continue

                    published_at = published_by_url.get(url) or parse_exa_published_date(
                        item.get("publishedDate")
                    )
                    extracting_payload: dict = {"url": url, "title": title}
                    if published_at:
                        extracting_payload["published_at"] = published_at.isoformat()
                    await log_and_emit(session, run_id, "extracting", extracting_payload)

                    try:
                        extraction = await llm.extract(
                            text,
                            title=title,
                            country=country,
                            step_logger=step_logger,
                        )
                    except Exception:
                        try:
                            extraction = await llm.extract(
                                text,
                                title=title,
                                country=country,
                                step_logger=step_logger,
                            )
                        except Exception:
                            await _emit_article_skipped(
                                session,
                                run_id,
                                url=url,
                                title=title,
                                reason="extraction_failed",
                            )
                            continue

                    target_department = format_department(department, country)
                    extracted_department = normalize_department(extraction.department, country)
                    if (
                        extracted_department
                        and target_department
                        and extracted_department != target_department
                    ):
                        continue

                    extraction.department = ensure_department(
                        extraction.department, department, country
                    )
                    if not extraction.sector:
                        extraction.sector = sector  # type: ignore[assignment]

                    if not extraction.is_relevant:
                        mark_url_seen(session, url, "not_relevant", run_id)
                        known_urls.add(url)
                        session.commit()
                        await log_and_emit(
                            session,
                            run_id,
                            "article_not_relevant",
                            {"url": url, "title": title, "name": extraction.name},
                        )
                        continue

                    company_resolution = CompanyResolution(matched=False)
                    if extraction.company and country == "FR":
                        await log_and_emit(
                            session,
                            run_id,
                            "company_searching",
                            {"company": extraction.company, "url": url},
                        )
                        company_resolution = await enrich_company(
                            extraction,
                            article_text=text,
                            country=country,
                            step_logger=step_logger,
                        )
                        if company_resolution.matched:
                            await log_and_emit(
                                session,
                                run_id,
                                "company_resolved",
                                {
                                    "siren": company_resolution.siren,
                                    "company_legal_name": company_resolution.company_legal_name,
                                },
                            )
                        else:
                            await log_and_emit(
                                session,
                                run_id,
                                "company_skipped",
                                {"reason": company_resolution.reason or "non identifié"},
                            )

                    project, is_new = upsert_project(
                        session,
                        extraction,
                        url=url,
                        title=title,
                        raw_excerpt=text[:2000],
                        run_id=run_id,
                        country=country,
                        company_resolution=company_resolution,
                        published_at=published_at,
                    )
                    session.commit()

                    known_urls.add(url)
                    run.articles_found += 1
                    if is_new:
                        run.projects_new += 1
                    else:
                        run.projects_updated += 1
                    session.commit()

                    await log_and_emit(
                        session,
                        run_id,
                        "project_found",
                        {
                            "project_id": str(project.id),
                            "name": project.name,
                            "is_new": is_new,
                        },
                    )

                    found_relevant = True
                    if test_single:
                        break

                if test_single and found_relevant:
                    break
            if test_single and run.articles_found > 0:
                break

        if test_single and run.articles_found == 0:
            run.status = "failed"
            run.error_message = "Aucun article pertinent trouvé en mode test"
            run.finished_at = datetime.now(timezone.utc)
            session.commit()
            await log_and_emit(
                session,
                run_id,
                "run_failed",
                {"error": run.error_message},
            )
            return run

        if not test_single:
            await log_and_emit(
                session, run_id, "deduplicating", {"message": "Consolidation des doublons…"}
            )
            merged_events = await run_dedup_pass(
                session, run, config.departments, country=country, step_logger=step_logger
            )
            for event in merged_events:
                await log_and_emit(session, run_id, "project_merged", event)

        run.status = "completed"
        run.finished_at = datetime.now(timezone.utc)
        session.commit()
        await log_and_emit(
            session,
            run_id,
            "run_completed",
            {
                "articles_found": run.articles_found,
                "projects_new": run.projects_new,
                "projects_updated": run.projects_updated,
                "projects_merged": run.projects_merged,
            },
        )
    except Exception as exc:
        session.rollback()
        run = session.get(Run, run_id)
        if run:
            run.status = "failed"
            run.error_message = str(exc)
            run.finished_at = datetime.now(timezone.utc)
            session.commit()
            await log_and_emit(session, run_id, "run_failed", {"error": str(exc)})
        raise

    return run
