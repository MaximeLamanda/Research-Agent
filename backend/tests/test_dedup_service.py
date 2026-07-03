import uuid

from app.agent.dedup_service import department_codes_for_run, resolve_dedup_targets
from app.models.config import Config
from app.models.project import Project
from app.models.run import Run
from app.models.source import Source


def test_department_codes_for_run_groups_by_country(db_session):
    run = Run(status="completed", mode="full")
    lidl = Project(
        name="Lidl Rheinfelden",
        city="Rheinfelden",
        department="BW - Baden-Württemberg",
        country="DE",
        match_key="lidl|rheinfelden",
    )
    amazon = Project(
        name="Amazon Lyon",
        city="Lyon",
        department="69 - Rhône",
        country="FR",
        match_key="amazon|lyon",
    )
    db_session.add_all([run, lidl, amazon])
    db_session.flush()
    db_session.add_all(
        [
            Source(project_id=lidl.id, url="https://example.com/de", run_id=run.id),
            Source(project_id=amazon.id, url="https://example.com/fr", run_id=run.id),
        ]
    )
    db_session.commit()

    grouped = department_codes_for_run(db_session, run.id)

    assert grouped == {"DE": ["BW"], "FR": ["69"]}


def test_resolve_dedup_targets_run_scope_uses_run_projects(db_session):
    run = Run(status="completed", mode="full")
    project = Project(
        name="Lidl Rheinfelden",
        city="Rheinfelden",
        department="BW — Baden-Württemberg",
        country="DE",
        match_key="lidl|rheinfelden",
    )
    db_session.add_all([run, project])
    db_session.flush()
    db_session.add(Source(project_id=project.id, url="https://example.com/lidl", run_id=run.id))
    db_session.commit()

    targets = resolve_dedup_targets(db_session, scope="run", run_id=run.id)

    assert targets == [("DE", ["BW"])]


def test_resolve_dedup_targets_explicit_departments(db_session):
    targets = resolve_dedup_targets(
        db_session,
        scope="run",
        run_id=uuid.uuid4(),
        departments=["69", "38"],
        country="FR",
    )

    assert targets == [("FR", ["69", "38"])]
