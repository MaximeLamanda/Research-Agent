from app.agent.queries import SECTOR_QUERIES


def test_sector_queries_include_department_name_and_label():
    query = SECTOR_QUERIES["logistique"].format(
        dept="69",
        dept_code="69",
        dept_label="69 - Rhône",
        dept_name="Rhône",
        anchor_segment="",
    )
    assert "Rhône" in query
    assert "69 - Rhône" in query
    assert "département 69" in query


def test_sector_queries_with_anchor_segment():
    query = SECTOR_QUERIES["logistique"].format(
        dept="69",
        dept_code="69",
        dept_label="69 - Rhône",
        dept_name="Rhône",
        anchor_segment=" autour de Lyon et Villeurbanne",
    )
    assert "autour de Lyon et Villeurbanne" in query
