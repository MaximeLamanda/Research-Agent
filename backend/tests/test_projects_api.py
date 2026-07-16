from app.models.project import Project


def test_list_projects_filters_by_multiple_departments(client, db_session):
    db_session.add(Project(name="A", department="77 - Seine-et-Marne", country="FR", match_key="a"))
    db_session.add(Project(name="B", department="69 - Rhône", country="FR", match_key="b"))
    db_session.add(Project(name="C", department="38 - Isère", country="FR", match_key="c"))
    db_session.commit()

    response = client.get(
        "/api/projects",
        params=[("departments", "77"), ("departments", "69"), ("country", "FR")],
    )
    assert response.status_code == 200
    names = {p["name"] for p in response.json()}
    assert names == {"A", "B"}


def test_list_projects_filters_by_country(client, db_session):
    db_session.add(Project(name="FR Project", country="FR", match_key="fr"))
    db_session.add(Project(name="DE Project", country="DE", match_key="de"))
    db_session.add(Project(name="Legacy", country=None, match_key="legacy"))
    db_session.commit()

    response = client.get("/api/projects", params={"country": "FR"})
    assert response.status_code == 200
    names = {p["name"] for p in response.json()}
    assert names == {"FR Project", "Legacy"}

    response = client.get("/api/projects", params={"country": "DE"})
    assert response.status_code == 200
    names = {p["name"] for p in response.json()}
    assert names == {"DE Project"}


def test_list_projects_empty_departments_returns_all(client, db_session):
    db_session.add(Project(name="A", department="77 - Seine-et-Marne", country="FR", match_key="a"))
    db_session.add(Project(name="B", department="69 - Rhône", country="FR", match_key="b"))
    db_session.add(Project(name="C", department="38 - Isère", country="FR", match_key="c"))
    db_session.commit()

    response = client.get("/api/projects", params={"country": "FR"})
    assert response.status_code == 200
    names = {p["name"] for p in response.json()}
    assert names == {"A", "B", "C"}
