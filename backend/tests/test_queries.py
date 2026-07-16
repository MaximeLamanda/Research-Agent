from app.agent.queries import SECTOR_QUERIES, SECTOR_QUERIES_BY_COUNTRY


def test_sector_queries_include_department_name_and_label():
    query = SECTOR_QUERIES["logistique"].format(
        dept="69",
        dept_code="69",
        dept_label="69 - Rhône",
        dept_name="Rhône",
    )
    assert "Rhône" in query
    assert "69 - Rhône" in query
    assert "département 69" in query
    assert "France" in query
    assert "autour de" not in query


def test_sector_queries_gb_english():
    q = SECTOR_QUERIES_BY_COUNTRY["GB"]["logistique"]
    assert "United Kingdom" in q
    assert "{dept_label}" in q
    assert "warehouse" in q.lower()


def test_sector_queries_ie_english():
    q = SECTOR_QUERIES_BY_COUNTRY["IE"]["industriel"]
    assert "Ireland" in q
    assert "{dept_name}" in q
