from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.agent.exa_client import ExaClient, parse_exa_published_date, published_dates_by_url
from app.models.run_step import RunStep
from app.models.source import Source


@dataclass
class BackfillReport:
    total_missing: int = 0
    from_extracted_data: int = 0
    from_run_steps: int = 0
    from_exa: int = 0
    still_missing: int = 0
    updated: int = 0


def _apply_published_at(source: Source, published_at: date) -> None:
    source.published_at = published_at
    extracted_data = dict(source.extracted_data or {})
    extracted_data["published_at"] = published_at.isoformat()
    source.extracted_data = extracted_data


def _parse_published_value(value: str | None) -> date | None:
    if not value:
        return None
    return parse_exa_published_date(str(value))


def build_published_dates_from_run_steps(session: Session) -> dict[str, date]:
    dates: dict[str, date] = {}
    steps = (
        session.query(RunStep)
        .filter(RunStep.step_type.in_(["extracting", "exa_fetch_done", "exa_search_done"]))
        .all()
    )

    for step in steps:
        data = step.data or {}
        if step.step_type == "extracting":
            url = data.get("url")
            parsed = _parse_published_value(data.get("published_at"))
            if url and parsed:
                dates[url] = parsed
            continue

        if step.step_type == "exa_fetch_done":
            articles = data.get("articles") or []
            for article in articles:
                url = article.get("url")
                parsed = _parse_published_value(article.get("published_at"))
                if url and parsed:
                    dates[url] = parsed
            continue

        for result in data.get("results") or []:
            url = result.get("url")
            parsed = _parse_published_value(result.get("published_at"))
            if url and parsed:
                dates[url] = parsed

    return dates


async def fetch_published_dates_from_exa(
    urls: list[str],
    *,
    api_key: str,
    batch_size: int = 50,
) -> dict[str, date]:
    if not api_key:
        raise ValueError("EXA_API_KEY is required to fetch published dates from Exa")

    client = ExaClient(api_key)
    dates: dict[str, date] = {}
    for index in range(0, len(urls), batch_size):
        batch = urls[index : index + batch_size]
        results = await client.fetch(batch, max_characters=100)
        dates.update(published_dates_by_url(results))
    return dates


def backfill_source_published_dates(
    session: Session,
    *,
    use_exa: bool = False,
    exa_api_key: str | None = None,
    dry_run: bool = False,
) -> BackfillReport:
    report = BackfillReport()
    sources = session.query(Source).filter(Source.published_at.is_(None)).all()
    report.total_missing = len(sources)
    if not sources:
        return report

    run_step_dates = build_published_dates_from_run_steps(session)
    pending_exa_urls: list[str] = []

    for source in sources:
        published_at = _parse_published_value((source.extracted_data or {}).get("published_at"))
        origin = "extracted_data" if published_at else None

        if not published_at:
            published_at = run_step_dates.get(source.url)
            if published_at:
                origin = "run_steps"

        if not published_at and use_exa:
            pending_exa_urls.append(source.url)
            continue

        if not published_at:
            report.still_missing += 1
            continue

        if origin == "extracted_data":
            report.from_extracted_data += 1
        elif origin == "run_steps":
            report.from_run_steps += 1

        if not dry_run:
            _apply_published_at(source, published_at)
            report.updated += 1

    if use_exa and pending_exa_urls:
        import asyncio

        exa_dates = asyncio.run(
            fetch_published_dates_from_exa(
                pending_exa_urls,
                api_key=exa_api_key or "",
            )
        )
        sources_by_url = {source.url: source for source in sources if source.url in pending_exa_urls}
        for url, published_at in exa_dates.items():
            source = sources_by_url.get(url)
            if not source or source.published_at is not None:
                continue
            report.from_exa += 1
            if not dry_run:
                _apply_published_at(source, published_at)
                report.updated += 1

        report.still_missing += len(pending_exa_urls) - report.from_exa

    if not dry_run and report.updated:
        session.commit()

    return report
