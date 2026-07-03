import asyncio
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.agent.dedup_service import run_dedup_for_run
from app.agent.pipeline import emit_event, get_run_queue, run_pipeline
from app.api.config import get_or_create_config
from app.db.session import SessionLocal, get_db
from app.models.project_merge import ProjectMerge
from app.models.project_update import ProjectUpdate
from app.models.run import Run
from app.models.source import Source
from app.api.serializers import source_to_read
from app.models.run_step import RunStep
from app.schemas import (
    ProjectMergeRead,
    ProjectUpdateRead,
    RunCreate,
    RunDedupCreate,
    RunDedupRead,
    RunRead,
    RunStepRead,
    SourceRead,
)

router = APIRouter(prefix="/api/runs", tags=["runs"])

# Runs whose background worker is alive in this process (empty after restart/reload).
_active_run_ids: set[uuid.UUID] = set()
_dedup_run_ids: set[uuid.UUID] = set()


def _fail_orphaned_run(run: Run, db: Session) -> None:
    run.status = "failed"
    run.error_message = "Interrupted (no active worker)"
    run.finished_at = datetime.now(timezone.utc)
    db.commit()


def _run_to_read(run: Run) -> RunRead:
    return RunRead(
        id=str(run.id),
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        articles_found=run.articles_found,
        projects_new=run.projects_new,
        projects_updated=run.projects_updated,
        projects_merged=run.projects_merged,
        error_message=run.error_message,
        created_at=run.created_at,
        mode=run.mode,
        geographical_granularity=run.geographical_granularity,
        exa_search_type=run.exa_search_type,
        exa_category=run.exa_category,
    )


def _execute_pipeline(run_id: uuid.UUID):
    _active_run_ids.add(run_id)
    db = SessionLocal()
    try:
        asyncio.run(run_pipeline(db, run_id=run_id))
    except Exception as exc:
        db.rollback()
        run = db.get(Run, run_id)
        if run and run.status == "in_progress":
            run.status = "failed"
            run.error_message = str(exc)
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        _active_run_ids.discard(run_id)
        db.close()


@router.post("", status_code=202, response_model=RunRead)
def trigger_run(
    background_tasks: BackgroundTasks,
    body: RunCreate | None = None,
    db: Session = Depends(get_db),
):
    in_progress = db.query(Run).filter(Run.status == "in_progress").first()
    if in_progress:
        if in_progress.id in _active_run_ids:
            raise HTTPException(status_code=409, detail="A run is already in progress")
        _fail_orphaned_run(in_progress, db)

    mode = body.mode if body else "full"
    config = get_or_create_config(db)
    run = Run(
        status="pending",
        mode=mode,
        geographical_granularity=config.geographical_granularity or "large",
        exa_search_type=config.exa_search_type or "auto",
        exa_category=config.exa_category or "news",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    run.status = "in_progress"
    if run.started_at is None:
        run.started_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)

    background_tasks.add_task(_execute_pipeline, run.id)
    return _run_to_read(run)


@router.get("", response_model=list[RunRead])
def list_runs(db: Session = Depends(get_db)):
    runs = db.query(Run).order_by(Run.created_at.desc()).limit(20).all()
    return [_run_to_read(r) for r in runs]


@router.get("/{run_id}", response_model=RunRead)
def get_run(run_id: uuid.UUID, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return _run_to_read(run)


def _merge_to_read(merge: ProjectMerge) -> ProjectMergeRead:
    return ProjectMergeRead(
        id=str(merge.id),
        run_id=str(merge.run_id) if merge.run_id else None,
        kept_project_id=str(merge.kept_project_id),
        absorbed_project_id=str(merge.absorbed_project_id),
        method=merge.method,
        score=merge.score,
        snapshot=merge.snapshot or {},
        created_at=merge.created_at,
    )


def _source_to_read(source: Source) -> SourceRead:
    return source_to_read(source)


@router.get("/{run_id}/sources", response_model=list[SourceRead])
def list_run_sources(run_id: uuid.UUID, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    sources = (
        db.query(Source)
        .filter(Source.run_id == run_id)
        .order_by(Source.created_at.desc())
        .all()
    )
    return [_source_to_read(source) for source in sources]


@router.get("/{run_id}/merges", response_model=list[ProjectMergeRead])
def list_run_merges(run_id: uuid.UUID, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    merges = (
        db.query(ProjectMerge)
        .filter(ProjectMerge.run_id == run_id)
        .order_by(ProjectMerge.created_at.desc())
        .all()
    )
    return [_merge_to_read(merge) for merge in merges]


def _update_to_read(update: ProjectUpdate) -> ProjectUpdateRead:
    return ProjectUpdateRead(
        id=str(update.id),
        run_id=str(update.run_id),
        project_id=str(update.project_id),
        project_name=update.project.name,
        source_id=str(update.source_id),
        source_url=update.source.url,
        source_title=update.source.title,
        changes=update.changes or [],
        created_at=update.created_at,
    )


@router.get("/{run_id}/updates", response_model=list[ProjectUpdateRead])
def list_run_updates(run_id: uuid.UUID, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    updates = (
        db.query(ProjectUpdate)
        .filter(ProjectUpdate.run_id == run_id)
        .order_by(ProjectUpdate.created_at.desc())
        .all()
    )
    return [_update_to_read(update) for update in updates]


@router.get("/{run_id}/steps", response_model=list[RunStepRead])
def list_run_steps(run_id: uuid.UUID, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    steps = (
        db.query(RunStep)
        .filter(RunStep.run_id == run_id)
        .order_by(RunStep.created_at.asc())
        .all()
    )
    return [
        RunStepRead(
            id=str(step.id),
            run_id=str(step.run_id),
            step_type=step.step_type,
            message=step.message,
            data=step.data or {},
            created_at=step.created_at,
        )
        for step in steps
    ]


def _execute_dedup(
    run_id: uuid.UUID,
    *,
    scope: str,
    departments: list[str] | None,
    country: str | None,
):
    from app.agent.dedup_service import resolve_dedup_targets

    _dedup_run_ids.add(run_id)
    db = SessionLocal()
    try:
        run = db.get(Run, run_id)
        if not run:
            return
        targets = resolve_dedup_targets(
            db,
            scope=scope,  # type: ignore[arg-type]
            run_id=run_id,
            departments=departments,
            country=country,
        )
        asyncio.run(
            run_dedup_for_run(
                db,
                run,
                scope=scope,  # type: ignore[arg-type]
                departments=departments,
                country=country,
            )
        )
        db.refresh(run)
        asyncio.run(
            emit_event(
                run_id,
                "dedup_completed",
                {
                    "run_id": str(run_id),
                    "projects_merged": run.projects_merged,
                    "targets": [
                        {"country": c, "departments": codes} for c, codes in targets
                    ],
                },
            )
        )
    except Exception as exc:
        db.rollback()
        asyncio.run(emit_event(run_id, "dedup_failed", {"run_id": str(run_id), "error": str(exc)}))
    finally:
        _dedup_run_ids.discard(run_id)
        db.close()


@router.post("/{run_id}/dedup", status_code=202, response_model=RunDedupRead)
def trigger_run_dedup(
    run_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    body: RunDedupCreate | None = None,
    db: Session = Depends(get_db),
):
    from app.agent.dedup_service import resolve_dedup_targets

    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status == "in_progress":
        raise HTTPException(status_code=409, detail="Run is still in progress")
    if run_id in _dedup_run_ids:
        raise HTTPException(status_code=409, detail="Dedup already in progress for this run")

    in_progress = db.query(Run).filter(Run.status == "in_progress").first()
    if in_progress and in_progress.id in _active_run_ids:
        raise HTTPException(status_code=409, detail="A run is already in progress")

    options = body or RunDedupCreate()
    targets = resolve_dedup_targets(
        db,
        scope=options.scope,
        run_id=run_id,
        departments=options.departments,
        country=options.country,
    )
    if not any(codes for _, codes in targets):
        raise HTTPException(status_code=400, detail="No departments to deduplicate")

    background_tasks.add_task(
        _execute_dedup,
        run_id,
        scope=options.scope,
        departments=options.departments,
        country=options.country,
    )
    return RunDedupRead(
        run_id=str(run_id),
        status="started",
        scope=options.scope,
        targets=[{"country": c, "departments": codes} for c, codes in targets],
    )


@router.get("/{run_id}/stream")
async def stream_run(run_id: uuid.UUID, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    queue = get_run_queue(str(run_id))

    async def event_generator():
        if run.status in ("completed", "failed"):
            yield {
                "event": f"run_{run.status}",
                "data": json.dumps(
                    {
                        "articles_found": run.articles_found,
                        "projects_new": run.projects_new,
                        "projects_updated": run.projects_updated,
                        "projects_merged": run.projects_merged,
                        "error": run.error_message,
                    }
                ),
            }
            return

        while True:
            try:
                message = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield {
                    "event": message["event"],
                    "data": json.dumps(message["data"]),
                }
                if message["event"] in ("run_completed", "run_failed"):
                    break
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "{}"}

    return EventSourceResponse(event_generator())
