import uuid

from sqlalchemy.orm import Session

from app.models.processed_url import ProcessedUrl
from app.models.run_step import RunStep
from app.models.source import Source


def load_known_urls(session: Session) -> set[str]:
    source_urls = {row[0] for row in session.query(Source.url).all()}
    processed_urls = {row[0] for row in session.query(ProcessedUrl.url).all()}
    return source_urls | processed_urls


def mark_url_seen(
    session: Session,
    url: str,
    reason: str,
    run_id: uuid.UUID | None = None,
) -> None:
    if session.query(ProcessedUrl.id).filter(ProcessedUrl.url == url).first():
        return
    session.add(ProcessedUrl(url=url, reason=reason, run_id=run_id))


def backfill_processed_urls_from_steps(session: Session) -> int:
    steps = (
        session.query(RunStep)
        .filter(RunStep.step_type == "article_not_relevant")
        .order_by(RunStep.created_at.asc())
        .all()
    )
    added = 0
    for step in steps:
        url = (step.data or {}).get("url")
        if not url:
            continue
        if session.query(ProcessedUrl.id).filter(ProcessedUrl.url == url).first():
            continue
        session.add(
            ProcessedUrl(url=url, reason="not_relevant", run_id=step.run_id)
        )
        added += 1
    if added:
        session.commit()
    return added
