from unittest.mock import AsyncMock, patch

import pytest

from app.agent.schemas import ProjectExtraction
from app.models.config import Config
from app.models.processed_url import ProcessedUrl
from app.models.run import Run


def _make_config():
    return Config(
        country="FR",
        departments=["69"],
        sectors=["industriel"],
        cron_day=0,
        cron_hour=6,
    )


@pytest.mark.asyncio
async def test_prefiltered_url_suppressed_on_next_run(db_session):
    config = _make_config()
    db_session.add(config)
    run1 = Run(status="in_progress")
    run2 = Run(status="in_progress")
    db_session.add_all([run1, run2])
    db_session.commit()

    rejected_url = "https://a.com/rejected"
    kept_url = "https://a.com/kept"
    search = [
        {"url": kept_url, "title": "Kept", "score": 0.9, "highlights": ["ok"]},
        {"url": rejected_url, "title": "Rejected", "score": 0.5, "highlights": ["voirie"]},
    ]
    decisions = {
        kept_url: (True, "ok"),
        rejected_url: (False, "voirie"),
    }

    fake_extraction = AsyncMock()
    fake_extraction.extract = AsyncMock(
        return_value=ProjectExtraction(is_relevant=False, name="skip")
    )
    fake_prefilter = AsyncMock()
    fake_prefilter.select = AsyncMock(return_value=decisions)

    with (
        patch("app.agent.pipeline.get_or_create_config", return_value=config),
        patch("app.agent.pipeline.ExaClient") as exa_cls,
        patch("app.agent.pipeline.LLMExtractor", return_value=fake_extraction),
        patch("app.agent.pipeline.UrlPrefilter", return_value=fake_prefilter),
        patch("app.agent.dedup_service.run_dedup_for_run", new_callable=AsyncMock, return_value=[]),
        patch("app.agent.pipeline.emit_event", new_callable=AsyncMock),
    ):
        exa = exa_cls.return_value
        exa.search = AsyncMock(return_value=search)
        exa.fetch = AsyncMock(return_value=[])

        from app.agent.pipeline import run_pipeline

        await run_pipeline(db_session, run_id=run1.id)

    processed = (
        db_session.query(ProcessedUrl)
        .filter(ProcessedUrl.url == rejected_url)
        .first()
    )
    assert processed is not None
    assert processed.reason == "prefiltered"

    with (
        patch("app.agent.pipeline.get_or_create_config", return_value=config),
        patch("app.agent.pipeline.ExaClient") as exa_cls,
        patch("app.agent.pipeline.LLMExtractor", return_value=fake_extraction),
        patch("app.agent.pipeline.UrlPrefilter", return_value=fake_prefilter),
        patch("app.agent.dedup_service.run_dedup_for_run", new_callable=AsyncMock, return_value=[]),
        patch("app.agent.pipeline.emit_event", new_callable=AsyncMock),
    ):
        exa = exa_cls.return_value
        exa.search = AsyncMock(return_value=search)
        exa.fetch = AsyncMock(return_value=[])

        from app.agent.pipeline import run_pipeline

        await run_pipeline(db_session, run_id=run2.id)

    assert exa.fetch.await_args.args[0] == [kept_url]
