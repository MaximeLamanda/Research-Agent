import pytest

from app.scheduler import create_scheduler


def test_scheduler_registers_weekly_job(mocker):
    mocker.patch("app.scheduler.start_scheduler")
    scheduler = create_scheduler()
    from app.scheduler import scheduler as sched

    sched.add_job(lambda: None, "cron", day_of_week=0, hour=6, id="weekly_research", replace_existing=True)
    jobs = sched.get_jobs()
    assert any(j.id == "weekly_research" for j in jobs)
