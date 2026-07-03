import uuid

from app.models.project import Project
from app.models.project_merge import ProjectMerge
from app.models.run import Run
from app.models.source import Source


def test_list_project_merges(client, db_session):
    run = Run(status="completed")
    kept = Project(name="Projet A", match_key="a|lyon")
    absorbed = Project(name="Projet B", match_key="b|lyon")
    db_session.add_all([run, kept, absorbed])
    db_session.flush()

    merge = ProjectMerge(
        run_id=run.id,
        kept_project_id=kept.id,
        absorbed_project_id=absorbed.id,
        method="fuzzy",
        score=0.95,
        snapshot={"absorbed": {"name": "Projet B"}},
    )
    db_session.add(merge)
    db_session.commit()

    response = client.get(f"/api/projects/{kept.id}/merges")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["method"] == "fuzzy"


def test_list_run_merges(client, db_session):
    run = Run(status="completed")
    kept = Project(name="Projet A", match_key="a|lyon")
    absorbed = Project(name="Projet B", match_key="b|lyon")
    db_session.add_all([run, kept, absorbed])
    db_session.flush()

    merge = ProjectMerge(
        run_id=run.id,
        kept_project_id=kept.id,
        absorbed_project_id=absorbed.id,
        method="llm",
        score=0.7,
        snapshot={},
    )
    db_session.add(merge)
    db_session.commit()

    response = client.get(f"/api/runs/{run.id}/merges")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_list_run_sources(client, db_session):
    run = Run(status="completed")
    project = Project(name="Projet A", match_key="a|lyon")
    db_session.add_all([run, project])
    db_session.flush()

    source = Source(
        project_id=project.id,
        run_id=run.id,
        url="https://example.com/article",
        title="Article test",
        extracted_data={"is_relevant": True, "name": "Projet A"},
    )
    db_session.add(source)
    db_session.commit()

    response = client.get(f"/api/runs/{run.id}/sources")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Article test"
    assert data[0]["url"] == "https://example.com/article"
    assert data[0]["is_relevant"] is True


def test_list_run_updates(client, db_session):
    run = Run(status="completed")
    project = Project(name="Projet A", match_key="a|lyon", status="conception")
    db_session.add_all([run, project])
    db_session.flush()

    source = Source(
        project_id=project.id,
        run_id=run.id,
        url="https://example.com/update-article",
        title="Article mise à jour",
    )
    db_session.add(source)
    db_session.flush()

    from app.models.project_update import ProjectUpdate

    update = ProjectUpdate(
        run_id=run.id,
        project_id=project.id,
        source_id=source.id,
        changes=[{"field": "status", "old": "conception", "new": "travaux"}],
    )
    db_session.add(update)
    db_session.commit()

    response = client.get(f"/api/runs/{run.id}/updates")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["project_name"] == "Projet A"
    assert data[0]["source_title"] == "Article mise à jour"
    assert data[0]["changes"][0]["field"] == "status"


def test_list_projects_includes_country(client, db_session):
    project = Project(
        name="Projet France",
        department="69 - Rhône",
        country="FR",
        match_key="a|lyon",
    )
    db_session.add(project)
    db_session.commit()

    response = client.get("/api/projects")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["country"] == "FR"

