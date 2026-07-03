from unittest.mock import AsyncMock, patch

import pytest

from app.agent.schemas import ProjectExtraction
from app.models.config import Config
from app.models.run import Run


def _keep_all_prefilter():
    prefilter = AsyncMock()
    prefilter.select = AsyncMock(
        side_effect=lambda candidates, step_logger=None: {
            c["url"]: (True, "") for c in candidates
        }
    )
    return prefilter


@pytest.mark.asyncio
async def test_test_single_mode_fails_when_no_relevant_article(db_session):
    config = Config(
        country="FR",
        departments=["69"],
        sectors=["industriel"],
        cron_day=0,
        cron_hour=6,
    )
    db_session.add(config)
    run = Run(status="in_progress", mode="test_single")
    db_session.add(run)
    db_session.commit()

    fake_search = [{"url": "https://a.com/1"}, {"url": "https://a.com/2"}]
    fake_fetch = [
        {"url": "https://a.com/1", "title": "A", "text": "x" * 120},
        {"url": "https://a.com/2", "title": "B", "text": "y" * 120},
    ]
    fake_extraction = AsyncMock()
    fake_extraction.extract = AsyncMock(
        return_value=ProjectExtraction(is_relevant=False, name="skip")
    )

    with (
        patch("app.agent.pipeline.get_or_create_config", return_value=config),
        patch("app.agent.pipeline.ExaClient") as exa_cls,
        patch("app.agent.pipeline.LLMExtractor", return_value=fake_extraction),
        patch("app.agent.pipeline.UrlPrefilter", return_value=_keep_all_prefilter()),
        patch("app.agent.pipeline.run_dedup_pass", new_callable=AsyncMock) as dedup,
        patch("app.agent.pipeline.emit_event", new_callable=AsyncMock),
    ):
        exa = exa_cls.return_value
        exa.search = AsyncMock(return_value=fake_search)
        exa.fetch = AsyncMock(return_value=fake_fetch)

        from app.agent.pipeline import run_pipeline

        await run_pipeline(db_session, run_id=run.id)

    exa.fetch.assert_awaited_once()
    fetched_urls = exa.fetch.await_args.args[0]
    assert fetched_urls == ["https://a.com/1", "https://a.com/2"]
    assert fake_extraction.extract.await_count == 2
    dedup.assert_not_awaited()
    db_session.refresh(run)
    assert run.status == "failed"
    assert run.articles_found == 0
    assert "pertinent" in (run.error_message or "").lower()


@pytest.mark.asyncio
async def test_test_single_mode_succeeds_with_relevant_article(db_session):
    config = Config(
        country="FR",
        departments=["69"],
        sectors=["industriel"],
        cron_day=0,
        cron_hour=6,
    )
    db_session.add(config)
    run = Run(status="in_progress", mode="test_single")
    db_session.add(run)
    db_session.commit()

    fake_search = [{"url": "https://a.com/1"}, {"url": "https://a.com/2"}]
    fake_fetch = [
        {"url": "https://a.com/1", "title": "Skip", "text": "x" * 120},
        {"url": "https://a.com/2", "title": "Good", "text": "y" * 120},
    ]
    fake_extraction = AsyncMock()
    fake_extraction.extract = AsyncMock(
        side_effect=[
            ProjectExtraction(is_relevant=False, name="skip"),
            ProjectExtraction(
                is_relevant=True,
                name="Entrepôt Lyon",
                city="Lyon",
                department="69 - Rhône",
                sector="industriel",
            ),
        ]
    )

    with (
        patch("app.agent.pipeline.get_or_create_config", return_value=config),
        patch("app.agent.pipeline.ExaClient") as exa_cls,
        patch("app.agent.pipeline.LLMExtractor", return_value=fake_extraction),
        patch("app.agent.pipeline.UrlPrefilter", return_value=_keep_all_prefilter()),
        patch("app.agent.pipeline.run_dedup_pass", new_callable=AsyncMock) as dedup,
        patch("app.agent.pipeline.emit_event", new_callable=AsyncMock),
    ):
        exa = exa_cls.return_value
        exa.search = AsyncMock(return_value=fake_search)
        exa.fetch = AsyncMock(return_value=fake_fetch)

        from app.agent.pipeline import run_pipeline

        await run_pipeline(db_session, run_id=run.id)

    assert fake_extraction.extract.await_count == 2
    dedup.assert_not_awaited()
    db_session.refresh(run)
    assert run.status == "completed"
    assert run.articles_found == 1
