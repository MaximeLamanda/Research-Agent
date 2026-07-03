import uuid

import pytest
from unittest.mock import AsyncMock

from app.agent.pipeline import (
    _exa_fetch_articles_payload,
    _exa_search_results_payload,
    log_and_emit,
    step_message,
)
from app.models.run import Run
from app.models.run_step import RunStep


def test_exa_search_results_payload():
    results = _exa_search_results_payload(
        [
            {
                "url": "https://example.com/a",
                "title": "Article A",
                "score": 0.91,
                "publishedDate": "2025-06-01",
                "highlights": ["Un extrait intéressant sur le projet."],
            },
            {"url": "", "title": "skip"},
        ]
    )
    assert len(results) == 1
    assert results[0]["url"] == "https://example.com/a"
    assert results[0]["title"] == "Article A"
    assert results[0]["score"] == 0.91
    assert results[0]["published_at"] == "2025-06-01"
    assert "extrait" in results[0]["snippet"]


def test_exa_fetch_articles_payload():
    articles = _exa_fetch_articles_payload(
        [
            {
                "url": "https://example.com/a",
                "title": "Article A",
                "text": "x" * 120,
                "publishedDate": "2025-06-01T12:00:00.000Z",
            },
            {"title": "no url"},
        ]
    )
    assert len(articles) == 1
    assert articles[0]["url"] == "https://example.com/a"
    assert articles[0]["text_length"] == 120
    assert articles[0]["published_at"] == "2025-06-01"


def test_step_message_searching():
    msg = step_message("searching", {"department": "69", "sector": "industriel"})
    assert "69" in msg
    assert "industriel" in msg


def test_step_message_llm_dedup_done_includes_reason_when_present():
    msg = step_message(
        "llm_dedup_done",
        {
            "duration_ms": 420,
            "same_project": False,
            "reason": "Adresses différentes dans la même commune.",
        },
    )
    assert "same=False" in msg
    assert "Adresses différentes" in msg


def test_step_message_llm_dedup_done_without_reason():
    msg = step_message(
        "llm_dedup_done",
        {"duration_ms": 120, "same_project": True},
    )
    assert "same=True" in msg
    assert "—" not in msg.split("same=True")[1]


@pytest.mark.asyncio
async def test_log_and_emit_persists_step(db_session):
    run = Run(status="in_progress", mode="full")
    db_session.add(run)
    db_session.commit()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.agent.pipeline.emit_event", AsyncMock())
        await log_and_emit(
            db_session,
            run.id,
            "extracting",
            {"url": "https://example.com", "title": "Test"},
        )

    steps = db_session.query(RunStep).filter(RunStep.run_id == run.id).all()
    assert len(steps) == 1
    assert steps[0].step_type == "extracting"
    assert steps[0].data["url"] == "https://example.com"
    assert "offset_ms" in steps[0].data


def test_run_step_model(db_session):
    run = Run(status="in_progress", mode="full")
    db_session.add(run)
    db_session.commit()

    step = RunStep(
        run_id=run.id,
        step_type="searching",
        message="Recherche articles — industriel (dept. 69)",
        data={"department": "69", "sector": "industriel", "query": "test query"},
    )
    db_session.add(step)
    db_session.commit()

    saved = db_session.query(RunStep).filter(RunStep.run_id == run.id).one()
    assert saved.step_type == "searching"
    assert saved.data["department"] == "69"
    assert saved.message is not None
