from app.data.project_backfill import backfill_project_countries
from app.models.config import Config
from app.models.project import Project


def test_backfill_project_countries_from_department(db_session):
    db_session.add(Config(id=1, country="FR", departments=["69"]))
    db_session.add_all(
        [
            Project(name="Projet A", department="69 - Rhône", match_key="a"),
            Project(name="Projet B", department="BY - Bayern", match_key="b"),
            Project(name="Projet C", department=None, match_key="c"),
        ]
    )
    db_session.commit()

    updated = backfill_project_countries(db_session)

    projects = {project.name: project.country for project in db_session.query(Project).all()}
    assert updated == 3
    assert projects["Projet A"] == "FR"
    assert projects["Projet B"] == "DE"
    assert projects["Projet C"] == "FR"


def test_backfill_project_countries_skips_filled(db_session):
    db_session.add(Config(id=1, country="FR", departments=["69"]))
    db_session.add(
        Project(name="Projet A", department="69 - Rhône", country="DE", match_key="a")
    )
    db_session.commit()

    updated = backfill_project_countries(db_session)

    assert updated == 0
    project = db_session.query(Project).one()
    assert project.country == "DE"
