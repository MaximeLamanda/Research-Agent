import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Literal

from sqlalchemy.orm import Session

from app.agent.dedup_agent import run_dedup_pass
from app.agent.pipeline import log_and_emit, make_step_logger
from app.api.config import get_or_create_config
from app.data.departments import ensure_department, infer_country_from_department
from app.models.project import Project
from app.models.run import Run
from app.models.source import Source

DedupScope = Literal["run", "config", "all"]


def department_codes_for_run(session: Session, run_id: uuid.UUID) -> dict[str, list[str]]:
    """Départements des projets touchés par le run, groupés par pays."""
    rows = (
        session.query(Project.department, Project.country)
        .join(Source, Source.project_id == Project.id)
        .filter(Source.run_id == run_id, Project.department.isnot(None))
        .distinct()
        .all()
    )
    buckets: dict[str, set[str]] = defaultdict(set)
    for department, country in rows:
        project_country = (country or infer_country_from_department(department) or "FR").upper()
        normalized = ensure_department(department, project_country)
        if not normalized:
            continue
        code = normalized.split(" - ", 1)[0].strip()
        if code:
            buckets[project_country].add(code)
    return {country: sorted(codes) for country, codes in buckets.items()}


def department_codes_all_active(session: Session) -> dict[str, list[str]]:
    """Tous les départements des projets actifs, groupés par pays."""
    rows = (
        session.query(Project.department, Project.country)
        .filter(Project.merged_into_id.is_(None), Project.department.isnot(None))
        .distinct()
        .all()
    )
    buckets: dict[str, set[str]] = defaultdict(set)
    for department, country in rows:
        project_country = (country or infer_country_from_department(department) or "FR").upper()
        normalized = ensure_department(department, project_country)
        if not normalized:
            continue
        code = normalized.split(" - ", 1)[0].strip()
        if code:
            buckets[project_country].add(code)
    return {country: sorted(codes) for country, codes in buckets.items()}


def resolve_dedup_targets(
    session: Session,
    *,
    scope: DedupScope = "run",
    run_id: uuid.UUID | None = None,
    departments: list[str] | None = None,
    country: str | None = None,
) -> list[tuple[str, list[str]]]:
    """
    Retourne une liste (country, department_codes) à traiter.
    Compare tous les projets actifs du département, pas seulement ceux du run.
    """
    config = get_or_create_config(session)
    default_country = (country or config.country or "FR").upper()

    if departments:
        return [(default_country, departments)]

    if scope == "config":
        return [(default_country, list(config.departments or []))]

    if scope == "all":
        grouped = department_codes_all_active(session)
        if grouped:
            return [(c, codes) for c, codes in sorted(grouped.items()) if codes]
        return [(default_country, list(config.departments or []))]

    if run_id is None:
        raise ValueError("run_id is required when scope is 'run'")

    grouped = department_codes_for_run(session, run_id)
    if grouped:
        return [(c, codes) for c, codes in sorted(grouped.items()) if codes]

    return [(default_country, list(config.departments or []))]


async def run_dedup_for_run(
    session: Session,
    run: Run,
    *,
    scope: DedupScope = "run",
    departments: list[str] | None = None,
    country: str | None = None,
    step_logger: Callable[[str, dict | None, int | None], Awaitable[None]] | None = None,
) -> list[dict]:
    targets = resolve_dedup_targets(
        session,
        scope=scope,
        run_id=run.id,
        departments=departments,
        country=country,
    )
    if not any(codes for _, codes in targets):
        return []

    logger = step_logger
    if logger is None:
        logger = make_step_logger(session, run.id)

    await logger("deduplicating", {"message": "Consolidation des doublons…", "scope": scope})

    merged_events: list[dict] = []
    for target_country, codes in targets:
        if not codes:
            continue
        events = await run_dedup_pass(
            session,
            run,
            codes,
            country=target_country,
            step_logger=logger,
        )
        for event in events:
            await logger("project_merged", event)
        merged_events.extend(events)

    session.commit()
    return merged_events
