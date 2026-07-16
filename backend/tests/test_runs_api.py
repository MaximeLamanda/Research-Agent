from unittest.mock import AsyncMock, patch
import uuid

from app.models.project import Project
from app.models.run import Run
from app.models.run_step import RunStep
from app.models.source import Source


def test_trigger_run(client):
    with patch("app.api.runs.run_pipeline", new_callable=AsyncMock):
        response = client.post("/api/runs")
    assert response.status_code == 202
    assert response.json()["status"] == "in_progress"


def test_trigger_run_conflict_when_actively_running(client, db_session):
    run = Run(status="in_progress")
    db_session.add(run)
    db_session.commit()

    from app.api.runs import _active_run_ids

    _active_run_ids.add(run.id)
    try:
        response = client.post("/api/runs")
        assert response.status_code == 409
        assert response.json()["detail"] == "A run is already in progress"
    finally:
        _active_run_ids.discard(run.id)


def test_trigger_run_recovers_orphaned_run(client, db_session):
    run = Run(status="in_progress")
    db_session.add(run)
    db_session.commit()

    with patch("app.api.runs.run_pipeline", new_callable=AsyncMock):
        response = client.post("/api/runs")

    assert response.status_code == 202
    db_session.refresh(run)
    assert run.status == "failed"
    assert run.error_message == "Interrupted (no active worker)"


def test_trigger_test_run(client):
    with patch("app.api.runs.run_pipeline", new_callable=AsyncMock):
        response = client.post("/api/runs", json={"mode": "test_single"})
    assert response.status_code == 202
    assert response.json()["mode"] == "test_single"


def test_trigger_run_snapshots_config_settings(client, db_session):
    from app.models.config import Config

    config = db_session.query(Config).first()
    if config is None:
        config = Config(departments=[])
        db_session.add(config)
    config.geographical_granularity = "large"
    config.exa_search_type = "neural"
    config.exa_category = "company"
    db_session.commit()

    with patch("app.api.runs.run_pipeline", new_callable=AsyncMock):
        response = client.post("/api/runs")

    assert response.status_code == 202
    body = response.json()
    assert body["geographical_granularity"] == "large"
    assert body["exa_search_type"] == "neural"
    assert body["exa_category"] == "company"


def test_list_run_steps(client, db_session):
    run = Run(status="completed", mode="full")
    db_session.add(run)
    db_session.flush()
    db_session.add(
        RunStep(
            run_id=run.id,
            step_type="searching",
            message="test",
            data={"department": "69"},
        )
    )
    db_session.commit()

    response = client.get(f"/api/runs/{run.id}/steps")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["step_type"] == "searching"


def test_list_runs(client):
    response = client.get("/api/runs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_trigger_run_dedup(client, db_session):
    run = Run(status="completed", mode="full")
    project = Project(
        name="Lidl Rheinfelden",
        city="Rheinfelden",
        department="BW - Baden-Württemberg",
        country="DE",
        match_key="lidl|rheinfelden",
    )
    db_session.add_all([run, project])
    db_session.flush()
    db_session.add(Source(project_id=project.id, url="https://example.com/lidl", run_id=run.id))
    db_session.commit()

    with patch("app.api.runs._execute_dedup") as execute_dedup:
        response = client.post(f"/api/runs/{run.id}/dedup")

    assert response.status_code == 202
    body = response.json()
    assert body["run_id"] == str(run.id)
    assert body["status"] == "started"
    assert body["scope"] == "run"
    assert body["targets"] == [{"country": "DE", "departments": ["BW"]}]
    execute_dedup.assert_called_once()


def test_stop_run(client, db_session):
    run = Run(status="in_progress", mode="full")
    db_session.add(run)
    db_session.commit()

    from app.api.runs import _active_run_ids

    _active_run_ids.add(run.id)
    try:
        response = client.post(f"/api/runs/{run.id}/stop")
        assert response.status_code == 202
        assert response.json()["status"] == "in_progress"
    finally:
        _active_run_ids.discard(run.id)


def test_stop_run_not_found(client):
    response = client.post(f"/api/runs/{uuid.uuid4()}/stop")
    assert response.status_code == 404


def test_stop_run_not_in_progress(client, db_session):
    run = Run(status="completed", mode="full")
    db_session.add(run)
    db_session.commit()

    response = client.post(f"/api/runs/{run.id}/stop")
    assert response.status_code == 409


def test_trigger_run_dedup_not_found(client):
    response = client.post(f"/api/runs/{uuid.uuid4()}/dedup")
    assert response.status_code == 404


def test_trigger_run_dedup_conflict_when_run_in_progress(client, db_session):
    run = Run(status="in_progress", mode="full")
    db_session.add(run)
    db_session.commit()

    response = client.post(f"/api/runs/{run.id}/dedup")
    assert response.status_code == 409

