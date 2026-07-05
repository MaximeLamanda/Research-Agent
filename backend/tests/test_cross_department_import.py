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
async def test_cross_department_imports_without_run_stats(db_session):
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

    fake_search = [{"url": "https://example.com/rhone", "title": "Amazon Lyon", "score": 0.9}]
    fake_fetch = [{"url": "https://example.com/rhone", "title": "Amazon Lyon", "text": "x" * 120}]
    emit_mock = AsyncMock()
    project_mock = SimpleNamespace(id=uuid4(), name="Amazon logistics warehouse")
    upsert_mock = MagicMock(return_value=(project_mock, True))

    with (
        patch("app.agent.pipeline.get_or_create_config", return_value=config),
        patch("app.agent.pipeline.ExaClient") as exa_cls,
        patch("app.agent.pipeline.LLMExtractor") as llm_cls,
        patch("app.agent.pipeline.UrlPrefilter", return_value=_keep_all_prefilter()),
        patch("app.agent.pipeline.upsert_project", upsert_mock) as upsert_patch,
        patch("app.agent.pipeline.run_dedup_pass", new_callable=AsyncMock),
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
                name="Amazon logistics warehouse",
                department="69 - Rhône",
                city="Colombier-Saugnieu",
            )
        )

        result = await run_pipeline(db_session, run_id=run.id)

    upsert_patch.assert_called_once()
    extraction_arg = upsert_patch.call_args.args[1]
    assert extraction_arg.department == "69 - Rhône"

    cross_events = [c for c in emit_mock.await_args_list if c.args[1] == "project_imported_cross_department"]
    assert len(cross_events) == 1
    payload = cross_events[0].args[2]
    assert payload["target_department"] == "77 - Seine-et-Marne"
    assert payload["extracted_department"] == "69 - Rhône"
    assert payload["project_id"] == str(project_mock.id)

    project_found = [c for c in emit_mock.await_args_list if c.args[1] == "project_found"]
    assert project_found == []

    db_session.refresh(result)
    assert result.articles_found == 0
    assert result.projects_new == 0
    assert result.projects_updated == 0

    processed = db_session.query(ProcessedUrl).filter(ProcessedUrl.url == "https://example.com/rhone").first()
    assert processed is not None
    assert processed.reason == "cross_department"
