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


def _search_results(n: int) -> list[dict]:
    return [
        {"url": f"https://a.com/{i}", "title": f"T{i}", "score": 1.0 - i * 0.01,
         "highlights": [f"snippet {i}"]}
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_search_requests_25_results_and_caps_fetch_to_10(db_session):
    config = _make_config()
    db_session.add(config)
    run = Run(status="in_progress")
    db_session.add(run)
    db_session.commit()

    search = _search_results(25)
    # Le préfiltre retient 15 URLs (0..14), rejette le reste.
    decisions = {
        f"https://a.com/{i}": (i < 15, "ok" if i < 15 else "hors sujet")
        for i in range(25)
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

        await run_pipeline(db_session, run_id=run.id)

    assert exa.search.await_args.kwargs["num_results"] == 25
    fetched_urls = exa.fetch.await_args.args[0]
    assert len(fetched_urls) == 10
    # Priorisées par score Exa décroissant → les 10 premiers indices retenus.
    assert fetched_urls == [f"https://a.com/{i}" for i in range(10)]


@pytest.mark.asyncio
async def test_prefilter_rejects_are_marked_processed(db_session):
    config = _make_config()
    db_session.add(config)
    run = Run(status="in_progress")
    db_session.add(run)
    db_session.commit()

    search = _search_results(3)
    decisions = {
        "https://a.com/0": (True, "ok"),
        "https://a.com/1": (False, "voirie"),
        "https://a.com/2": (False, "inauguration"),
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

        await run_pipeline(db_session, run_id=run.id)

    assert exa.fetch.await_args.args[0] == ["https://a.com/0"]
    # Les rejets du préfiltre sont enregistrés en ProcessedUrl (exclusion définitive).
    processed = {row[0] for row in db_session.query(ProcessedUrl.url).all()}
    assert "https://a.com/1" in processed
    assert "https://a.com/2" in processed
    rows = (
        db_session.query(ProcessedUrl)
        .filter(ProcessedUrl.url.in_(["https://a.com/1", "https://a.com/2"]))
        .all()
    )
    assert all(r.reason == "prefiltered" for r in rows)
    # Un step article_skipped(prefiltered) est loggé pour chaque rejet.
    from app.models.run_step import RunStep

    skips = (
        db_session.query(RunStep)
        .filter(RunStep.run_id == run.id, RunStep.step_type == "article_skipped")
        .all()
    )
    reasons = {(s.data or {}).get("url"): (s.data or {}).get("reason") for s in skips}
    assert reasons.get("https://a.com/1") == "prefiltered"
    assert reasons.get("https://a.com/2") == "prefiltered"
    prefilter_details = {
        (s.data or {}).get("url"): (s.data or {}).get("prefilter_reason") for s in skips
    }
    assert prefilter_details.get("https://a.com/1") == "voirie"
    assert prefilter_details.get("https://a.com/2") == "inauguration"


@pytest.mark.asyncio
async def test_prefilter_failure_falls_back_to_top_10(db_session):
    config = _make_config()
    db_session.add(config)
    run = Run(status="in_progress")
    db_session.add(run)
    db_session.commit()

    search = _search_results(15)
    fake_extraction = AsyncMock()
    fake_extraction.extract = AsyncMock(
        return_value=ProjectExtraction(is_relevant=False, name="skip")
    )
    fake_prefilter = AsyncMock()
    fake_prefilter.select = AsyncMock(side_effect=RuntimeError("llm down"))

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

        await run_pipeline(db_session, run_id=run.id)

    # Fallback : les 10 premières URLs dans l'ordre Exa, run non échoué.
    assert exa.fetch.await_args.args[0] == [f"https://a.com/{i}" for i in range(10)]
    db_session.refresh(run)
    assert run.status == "completed"
    # Un step prefilter_failed est loggé pour tracer le fallback.
    from app.models.run_step import RunStep

    failed_steps = (
        db_session.query(RunStep)
        .filter(RunStep.run_id == run.id, RunStep.step_type == "prefilter_failed")
        .all()
    )
    assert len(failed_steps) == 1
    data = failed_steps[0].data or {}
    assert data.get("fallback_count") == 10
    assert "llm down" in data.get("error", "")
