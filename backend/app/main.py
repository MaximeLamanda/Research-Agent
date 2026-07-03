from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api import config, gis, projects, runs, search_anchors
from app.data.project_backfill import backfill_project_countries
from app.agent.known_urls import backfill_processed_urls_from_steps
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.config import settings
from app.models.run import Run  # noqa: F401 — register ORM models for create_all
from app.models import ProcessedUrl  # noqa: F401
from app.scheduler import start_scheduler, stop_scheduler


def _migrate_schema() -> None:
    inspector = inspect(engine)
    if not inspector.has_table("config"):
        return

    columns = {column["name"] for column in inspector.get_columns("config")}
    with engine.begin() as connection:
        if "exa_search_type" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE config ADD COLUMN exa_search_type VARCHAR NOT NULL DEFAULT 'auto'"
                )
            )
        if "exa_category" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE config ADD COLUMN exa_category VARCHAR NOT NULL DEFAULT 'news'"
                )
            )
        if "exa_start_published_date" not in columns:
            connection.execute(
                text("ALTER TABLE config ADD COLUMN exa_start_published_date DATE")
            )
        if "exa_end_published_date" not in columns:
            connection.execute(
                text("ALTER TABLE config ADD COLUMN exa_end_published_date DATE")
            )
        if "exa_published_date_preset" not in columns:
            connection.execute(
                text("ALTER TABLE config ADD COLUMN exa_published_date_preset VARCHAR")
            )
        if "country" not in columns:
            connection.execute(
                text("ALTER TABLE config ADD COLUMN country VARCHAR NOT NULL DEFAULT 'FR'")
            )
        if "region_cities" not in columns:
            connection.execute(
                text("ALTER TABLE config ADD COLUMN region_cities JSON NOT NULL DEFAULT '{}'")
            )
        if "geographical_granularity" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE config ADD COLUMN geographical_granularity VARCHAR NOT NULL DEFAULT 'large'"
                )
            )

    if inspector.has_table("projects"):
        project_columns = {column["name"] for column in inspector.get_columns("projects")}
        with engine.begin() as connection:
            if "merged_into_id" not in project_columns:
                connection.execute(text("ALTER TABLE projects ADD COLUMN merged_into_id CHAR(32)"))
            if "lead_pitch" not in project_columns:
                connection.execute(text("ALTER TABLE projects ADD COLUMN lead_pitch VARCHAR"))
            if "country" not in project_columns:
                connection.execute(text("ALTER TABLE projects ADD COLUMN country VARCHAR"))
            if "siren" not in project_columns:
                connection.execute(text("ALTER TABLE projects ADD COLUMN siren VARCHAR"))
            if "company_legal_name" not in project_columns:
                connection.execute(text("ALTER TABLE projects ADD COLUMN company_legal_name VARCHAR"))
            if "naf_code" not in project_columns:
                connection.execute(text("ALTER TABLE projects ADD COLUMN naf_code VARCHAR"))
            delivery_date_col = next(
                (col for col in inspector.get_columns("projects") if col["name"] == "delivery_date"),
                None,
            )
            if (
                delivery_date_col
                and "VARCHAR" not in str(delivery_date_col["type"]).upper()
                and engine.dialect.name == "postgresql"
            ):
                connection.execute(
                    text(
                        "ALTER TABLE projects ALTER COLUMN delivery_date TYPE VARCHAR "
                        "USING delivery_date::text"
                    )
                )

    if inspector.has_table("runs"):
        run_columns = {column["name"] for column in inspector.get_columns("runs")}
        with engine.begin() as connection:
            if "projects_merged" not in run_columns:
                connection.execute(
                    text("ALTER TABLE runs ADD COLUMN projects_merged INTEGER NOT NULL DEFAULT 0")
                )
            if "mode" not in run_columns:
                connection.execute(
                    text("ALTER TABLE runs ADD COLUMN mode VARCHAR NOT NULL DEFAULT 'full'")
                )
            if "geographical_granularity" not in run_columns:
                connection.execute(
                    text(
                        "ALTER TABLE runs ADD COLUMN geographical_granularity "
                        "VARCHAR NOT NULL DEFAULT 'large'"
                    )
                )
            if "exa_search_type" not in run_columns:
                connection.execute(
                    text(
                        "ALTER TABLE runs ADD COLUMN exa_search_type "
                        "VARCHAR NOT NULL DEFAULT 'auto'"
                    )
                )
            if "exa_category" not in run_columns:
                connection.execute(
                    text(
                        "ALTER TABLE runs ADD COLUMN exa_category "
                        "VARCHAR NOT NULL DEFAULT 'news'"
                    )
                )


def _cleanup_stale_runs() -> None:
    db = SessionLocal()
    try:
        stuck = db.query(Run).filter(Run.status == "in_progress").all()
        for run in stuck:
            run.status = "failed"
            run.error_message = "Interrupted (server restart)"
            run.finished_at = datetime.now(timezone.utc)
        if stuck:
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.testing:
        Base.metadata.create_all(bind=engine)
        _migrate_schema()
        _cleanup_stale_runs()
        backfill_project_countries(SessionLocal())
        backfill_processed_urls_from_steps(SessionLocal())
        start_scheduler()
    yield
    if not settings.testing:
        stop_scheduler()


app = FastAPI(title="Research Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(config.router)
app.include_router(search_anchors.router)
app.include_router(runs.router)
app.include_router(projects.router)
app.include_router(gis.router)


@app.get("/health")
def health():
    return {"status": "ok"}
