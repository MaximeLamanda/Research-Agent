import asyncio
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.agent.pipeline import run_pipeline
from app.api.config import get_or_create_config
from app.db.session import SessionLocal

scheduler = BackgroundScheduler()


def _weekly_job():
    db = SessionLocal()
    try:
        from app.models.run import Run

        in_progress = db.query(Run).filter(Run.status == "in_progress").first()
        if in_progress:
            return
        asyncio.run(run_pipeline(db))
    finally:
        db.close()


def create_scheduler() -> BackgroundScheduler:
    return scheduler


def start_scheduler():
    db = SessionLocal()
    try:
        config = get_or_create_config(db)
        scheduler.add_job(
            _weekly_job,
            CronTrigger(day_of_week=config.cron_day, hour=config.cron_hour, minute=0),
            id="weekly_research",
            replace_existing=True,
        )
        if not scheduler.running:
            scheduler.start()
    finally:
        db.close()


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
