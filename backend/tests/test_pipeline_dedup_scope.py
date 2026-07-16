"""Dédup automatique en fin de pipeline : périmètre basé sur le run, pas seulement la config."""
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.agent.pipeline import run_pipeline
from app.agent.schemas import ProjectExtraction
from app.models.config import Config
from app.models.project import Project
from app.models.run import Run
from app.models.source import Source


def _keep_all_prefilter():
    prefilter = AsyncMock()
    prefilter.select = AsyncMock(
        side_effect=lambda candidates, step_logger=None, country="FR": {
            c["url"]: (True, "") for c in candidates
        }
    )
    return prefilter


@pytest.mark.asyncio
async def test_pipeline_dedup_uses_run_scope_not_config_departments_only(db_session):
    """Un run UKE qui importe en UKJ doit dédupliquer UKJ, pas seulement UKE."""
    config = Config(
        country="GB",
        departments=["UKE"],
        sectors=["industriel"],
        cron_day=0,
        cron_hour=6,
    )
    db_session.add(config)
    run = Run(status="in_progress", mode="full")
    db_session.add(run)
    db_session.commit()

    fake_search = [{"url": "https://example.com/southampton", "title": "T Park", "score": 0.9}]
    fake_fetch = [
        {
            "url": "https://example.com/southampton",
            "title": "T Park Southampton",
            "text": "x" * 120,
        }
    ]

    with (
        patch("app.agent.pipeline.get_or_create_config", return_value=config),
        patch("app.agent.pipeline.ExaClient") as exa_cls,
        patch("app.agent.pipeline.LLMExtractor") as llm_cls,
        patch("app.agent.pipeline.UrlPrefilter", return_value=_keep_all_prefilter()),
        patch("app.agent.pipeline.upsert_project") as upsert_mock,
        patch("app.agent.dedup_service.run_dedup_for_run", new_callable=AsyncMock) as dedup_mock,
        patch("app.agent.pipeline.emit_event", new_callable=AsyncMock),
    ):
        exa = exa_cls.return_value
        exa.search = AsyncMock(return_value=fake_search)
        exa.fetch = AsyncMock(return_value=fake_fetch)
        llm_cls.return_value.extract = AsyncMock(
            return_value=ProjectExtraction(
                is_relevant=True,
                name="T Park Southampton",
                department="UKJ - South East",
                city="Southampton",
                company="Panattoni",
                sector="industriel",
            )
        )
        project = Project(
            id=uuid4(),
            name="T Park Southampton",
            city="Southampton",
            department="UKJ - South East",
            country="GB",
            company="Panattoni",
            match_key="park|southampton",
        )
        upsert_mock.return_value = (project, True)

        await run_pipeline(db_session, run_id=run.id)

    dedup_mock.assert_awaited_once()
    assert dedup_mock.await_args.kwargs["scope"] == "run"
    assert dedup_mock.await_args.kwargs["country"] == "GB"


@pytest.mark.asyncio
async def test_pipeline_dedup_merges_cross_department_imports_in_run(db_session):
    """Scénario Panattoni : deux fiches UKJ importées dans un run UKE fusionnées auto."""
    from app.agent.dedup_agent import run_dedup_pass

    config = Config(
        country="GB",
        departments=["UKE"],
        sectors=["industriel"],
        cron_day=0,
        cron_hour=6,
    )
    run = Run(status="in_progress")
    kept = Project(
        name="Panattoni T Park, Southampton",
        city="Southampton",
        department="UKJ - South East",
        country="GB",
        company="Panattoni",
        address="Salisbury Road, Totton",
        match_key="panattoni|park|southampton",
    )
    absorbed = Project(
        name="T Park Southampton",
        city="Southampton",
        department="UKJ - South East",
        country="GB",
        company="Panattoni",
        match_key="park|southampton",
    )
    db_session.add_all([config, run, kept, absorbed])
    db_session.flush()
    db_session.add_all(
        [
            Source(
                project_id=kept.id,
                url="https://example.com/panattoni-a",
                run_id=run.id,
            ),
            Source(
                project_id=absorbed.id,
                url="https://example.com/panattoni-b",
                run_id=run.id,
            ),
        ]
    )
    db_session.commit()

    events = await run_dedup_pass(db_session, run, ["UKJ"], country="GB")

    assert len(events) == 1
    assert events[0]["kept_name"] == "Panattoni T Park, Southampton"
    assert events[0]["absorbed_name"] == "T Park Southampton"
    db_session.refresh(absorbed)
    assert absorbed.merged_into_id == kept.id
