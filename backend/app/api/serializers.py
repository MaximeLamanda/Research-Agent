from app.models.source import Source
from app.schemas import SourceRead


def source_is_relevant(source: Source) -> bool | None:
    if not source.extracted_data:
        return None
    value = source.extracted_data.get("is_relevant")
    if value is None:
        return None
    return bool(value)


def source_to_read(source: Source) -> SourceRead:
    return SourceRead(
        id=str(source.id),
        url=source.url,
        title=source.title,
        published_at=source.published_at,
        created_at=source.created_at,
        run_id=str(source.run_id) if source.run_id else None,
        run_started_at=(source.run.started_at or source.run.created_at) if source.run else None,
        is_relevant=source_is_relevant(source),
    )
