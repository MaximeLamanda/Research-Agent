from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.agent.pipeline import run_pipeline
from app.models.config import Config
from app.models.processed_url import ProcessedUrl
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
async def test_emits_article_skipped_for_known_url_at_search_time(db_session):
    config = Config(
        country="FR",
        departments=["69"],
        sectors=["industriel"],
        cron_day=0,
        cron_hour=6,
    )
    db_session.add(config)
    db_session.add(
        ProcessedUrl(url="https://example.com/known", reason="not_relevant")
    )
    run = Run(status="in_progress", mode="test_single")
    db_session.add(run)
    db_session.commit()

    fake_search = [
        {"url": "https://example.com/known", "title": "Known", "score": 0.9},
        {"url": "https://example.com/new", "title": "New", "score": 0.8},
    ]
    fake_fetch = [
        {"url": "https://example.com/new", "title": "New", "text": "x" * 120},
    ]
    emit_mock = AsyncMock()

    with (
        patch("app.agent.pipeline.get_or_create_config", return_value=config),
        patch("app.agent.pipeline.ExaClient") as exa_cls,
        patch("app.agent.pipeline.LLMExtractor") as llm_cls,
        patch("app.agent.pipeline.UrlPrefilter", return_value=_keep_all_prefilter()),
        patch("app.agent.dedup_service.run_dedup_for_run", new_callable=AsyncMock),
        patch("app.agent.pipeline.emit_event", emit_mock),
    ):
        exa = exa_cls.return_value
        exa.search = AsyncMock(return_value=fake_search)
        exa.fetch = AsyncMock(return_value=fake_fetch)
        llm_cls.return_value.extract = AsyncMock(
            return_value=__import__(
                "app.agent.schemas", fromlist=["ProjectExtraction"]
            ).ProjectExtraction(is_relevant=True, name="Test", city="Lyon")
        )

        await run_pipeline(db_session, run_id=run.id)

    skipped = [
        c
        for c in emit_mock.await_args_list
        if c.args[1] == "article_skipped"
    ]
    assert len(skipped) == 1
    payload = skipped[0].args[2]
    assert payload["url"] == "https://example.com/known"
    assert payload["reason"] == "known"


@pytest.mark.asyncio
async def test_emits_article_skipped_for_short_text(db_session):
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

    fake_search = [{"url": "https://example.com/short", "title": "Short", "score": 0.7}]
    fake_fetch = [{"url": "https://example.com/short", "title": "Short", "text": "tiny"}]
    emit_mock = AsyncMock()

    with (
        patch("app.agent.pipeline.get_or_create_config", return_value=config),
        patch("app.agent.pipeline.ExaClient") as exa_cls,
        patch("app.agent.pipeline.LLMExtractor") as llm_cls,
        patch("app.agent.pipeline.UrlPrefilter", return_value=_keep_all_prefilter()),
        patch("app.agent.dedup_service.run_dedup_for_run", new_callable=AsyncMock),
        patch("app.agent.pipeline.emit_event", emit_mock),
    ):
        exa = exa_cls.return_value
        exa.search = AsyncMock(return_value=fake_search)
        exa.fetch = AsyncMock(return_value=fake_fetch)
        llm_cls.return_value.extract = AsyncMock()

        await run_pipeline(db_session, run_id=run.id)

    skipped = [
        c.args[2]
        for c in emit_mock.await_args_list
        if c.args[1] == "article_skipped"
    ]
    assert any(s["reason"] == "short_text" for s in skipped)
    llm_cls.return_value.extract.assert_not_awaited()


@pytest.mark.asyncio
async def test_null_extracted_department_falls_back_and_does_not_skip(db_session):
    config = Config(
        country="FR",
        departments=["77"],
        sectors=["industriel"],
        cron_day=0,
        cron_hour=6,
    )
    db_session.add(config)
    run = Run(status="in_progress", mode="test_single")
    db_session.add(run)
    db_session.commit()

    fake_search = [{"url": "https://example.com/new", "title": "New", "score": 0.8}]
    fake_fetch = [{"url": "https://example.com/new", "title": "New", "text": "x" * 120}]
    emit_mock = AsyncMock()
    project_mock = SimpleNamespace(id=uuid4(), name="Local project")
    upsert_mock = MagicMock(return_value=(project_mock, True))

    with (
        patch("app.agent.pipeline.get_or_create_config", return_value=config),
        patch("app.agent.pipeline.ExaClient") as exa_cls,
        patch("app.agent.pipeline.LLMExtractor") as llm_cls,
        patch("app.agent.pipeline.UrlPrefilter", return_value=_keep_all_prefilter()),
        patch("app.agent.pipeline.upsert_project", upsert_mock),
        patch("app.agent.dedup_service.run_dedup_for_run", new_callable=AsyncMock),
        patch("app.agent.pipeline.emit_event", emit_mock),
    ):
        exa = exa_cls.return_value
        exa.search = AsyncMock(return_value=fake_search)
        exa.fetch = AsyncMock(return_value=fake_fetch)
        llm_cls.return_value.extract = AsyncMock(
            return_value=__import__(
                "app.agent.schemas", fromlist=["ProjectExtraction"]
            ).ProjectExtraction(
                is_relevant=True,
                name="Local project",
                department=None,
                city="Meaux",
            )
        )

        await run_pipeline(db_session, run_id=run.id)

    wrong = [
        c.args[2]
        for c in emit_mock.await_args_list
        if c.args[1] == "article_skipped" and c.args[2].get("reason") == "wrong_department"
    ]
    assert wrong == []
    upsert_mock.assert_called_once()


@pytest.mark.asyncio
async def test_emits_article_skipped_for_foreign_location(db_session):
    config = Config(
        country="FR",
        departments=["77"],
        sectors=["industriel"],
        cron_day=0,
        cron_hour=6,
    )
    db_session.add(config)
    run = Run(status="in_progress", mode="test_single")
    db_session.add(run)
    db_session.commit()

    fake_search = [{"url": "https://example.com/korea", "title": "LivsMed facility", "score": 0.9}]
    fake_fetch = [{"url": "https://example.com/korea", "title": "LivsMed facility", "text": "x" * 120}]
    emit_mock = AsyncMock()
    upsert_mock = MagicMock()

    with (
        patch("app.agent.pipeline.get_or_create_config", return_value=config),
        patch("app.agent.pipeline.ExaClient") as exa_cls,
        patch("app.agent.pipeline.LLMExtractor") as llm_cls,
        patch("app.agent.pipeline.UrlPrefilter", return_value=_keep_all_prefilter()),
        patch("app.agent.pipeline.upsert_project", upsert_mock),
        patch("app.agent.dedup_service.run_dedup_for_run", new_callable=AsyncMock),
        patch("app.agent.pipeline.emit_event", emit_mock),
    ):
        exa = exa_cls.return_value
        exa.search = AsyncMock(return_value=fake_search)
        exa.fetch = AsyncMock(return_value=fake_fetch)
        llm_cls.return_value.extract = AsyncMock(
            return_value=__import__(
                "app.agent.schemas", fromlist=["ProjectExtraction"]
            ).ProjectExtraction(
                is_relevant=True,
                name="LivsMed facility",
                city="Yongin",
                department="77 - Seine-et-Marne",
                address="727 Jigok-dong, Giheung-gu, Yongin, Gyeonggi, South Korea",
            )
        )

        await run_pipeline(db_session, run_id=run.id)

    skipped = [
        c.args[2]
        for c in emit_mock.await_args_list
        if c.args[1] == "article_skipped"
    ]
    assert len(skipped) == 1
    assert skipped[0]["reason"] == "foreign_location"
    assert skipped[0]["city"] == "Yongin"
    assert skipped[0]["url"] == "https://example.com/korea"

    upsert_mock.assert_not_called()

    processed = db_session.query(ProcessedUrl).filter(
        ProcessedUrl.url == "https://example.com/korea"
    ).first()
    assert processed is not None
    assert processed.reason == "foreign_location"
