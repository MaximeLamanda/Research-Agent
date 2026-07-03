import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.known_urls import backfill_processed_urls_from_steps, load_known_urls, mark_url_seen
from app.agent.schemas import ProjectExtraction
from app.models.config import Config
from app.models.processed_url import ProcessedUrl
from app.models.run import Run
from app.models.run_step import RunStep


def test_load_known_urls_includes_sources_and_processed(db_session):
    db_session.add(ProcessedUrl(url="https://example.com/skip", reason="not_relevant"))
    db_session.commit()

    known = load_known_urls(db_session)

    assert "https://example.com/skip" in known


def test_mark_url_seen_is_idempotent(db_session):
    mark_url_seen(db_session, "https://example.com/a", "not_relevant")
    db_session.commit()
    mark_url_seen(db_session, "https://example.com/a", "not_relevant")
    db_session.commit()

    assert (
        db_session.query(ProcessedUrl).filter(ProcessedUrl.url == "https://example.com/a").count()
        == 1
    )


def test_backfill_processed_urls_from_steps(db_session):
    run_id = uuid.uuid4()
    db_session.add(
        RunStep(
            run_id=run_id,
            step_type="article_not_relevant",
            message="skip",
            data={"url": "https://example.com/old-skip", "title": "Old"},
        )
    )
    db_session.commit()

    added = backfill_processed_urls_from_steps(db_session)

    assert added == 1
    assert (
        db_session.query(ProcessedUrl)
        .filter(ProcessedUrl.url == "https://example.com/old-skip")
        .one()
        .reason
        == "not_relevant"
    )


@pytest.mark.asyncio
async def test_second_run_skips_persisted_non_relevant_url(db_session):
    config = Config(
        country="FR",
        departments=["69"],
        sectors=["industriel"],
        cron_day=0,
        cron_hour=6,
    )
    db_session.add(config)
    db_session.add(
        ProcessedUrl(
            url="https://a.com/1",
            reason="not_relevant",
        )
    )
    run = Run(status="in_progress", mode="test_single")
    db_session.add(run)
    db_session.commit()

    fake_search = [{"url": "https://a.com/1"}, {"url": "https://a.com/2"}]
    fake_fetch = [{"url": "https://a.com/2", "title": "Good", "text": "y" * 120}]
    fake_extraction = AsyncMock()
    fake_extraction.extract = AsyncMock(
        return_value=ProjectExtraction(
            is_relevant=True,
            name="Entrepôt Lyon",
            city="Lyon",
            department="69 - Rhône",
            sector="industriel",
        )
    )

    keep_all_prefilter = AsyncMock()
    keep_all_prefilter.select = AsyncMock(
        side_effect=lambda candidates, step_logger=None: {
            c["url"]: (True, "") for c in candidates
        }
    )

    with (
        patch("app.agent.pipeline.get_or_create_config", return_value=config),
        patch("app.agent.pipeline.ExaClient") as exa_cls,
        patch("app.agent.pipeline.LLMExtractor", return_value=fake_extraction),
        patch("app.agent.pipeline.UrlPrefilter", return_value=keep_all_prefilter),
        patch("app.agent.pipeline.run_dedup_pass", new_callable=AsyncMock),
        patch("app.agent.pipeline.emit_event", new_callable=AsyncMock),
    ):
        exa = exa_cls.return_value
        exa.search = AsyncMock(return_value=fake_search)
        exa.fetch = AsyncMock(return_value=fake_fetch)

        from app.agent.pipeline import run_pipeline

        await run_pipeline(db_session, run_id=run.id)

    exa.fetch.assert_awaited_once_with(["https://a.com/2"])
    fake_extraction.extract.assert_awaited_once()
    db_session.refresh(run)
    assert run.status == "completed"
    assert run.articles_found == 1
