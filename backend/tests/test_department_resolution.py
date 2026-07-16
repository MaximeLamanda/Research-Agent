from app.agent.department_resolution import (
    department_from_anchor_city,
    is_foreign_location,
    resolve_extraction_department,
)
from app.agent.schemas import ProjectExtraction


def test_department_from_anchor_city_meaux():
    assert department_from_anchor_city("Meaux", "FR") == "77"


def test_department_from_anchor_city_lyon():
    assert department_from_anchor_city("Lyon", "FR") == "69"


def test_department_from_anchor_city_unknown():
    assert department_from_anchor_city("Yongin", "FR") is None


def test_is_foreign_location_korea():
    assert is_foreign_location(
        "Yongin",
        "727 Jigok-dong, Giheung-gu, Yongin, Gyeonggi, South Korea",
        "",
    )


def test_is_foreign_location_sweden():
    assert is_foreign_location("Södertälje", "Stockholm Syd, Sweden", "")


def test_is_foreign_location_french_city():
    assert not is_foreign_location("Meaux", "Zone industrielle, Meaux", "Seine-et-Marne")


def test_is_foreign_location_gb_allows_london():
    assert is_foreign_location("London", "1 High Street", "", country="GB") is False


def test_is_foreign_location_gb_rejects_france():
    assert is_foreign_location("Lyon", "France", "projet à Lyon France", country="GB") is True


def test_is_foreign_location_ie_allows_dublin():
    assert is_foreign_location("Dublin", None, "", country="IE") is False


def test_resolve_overrides_hallucinated_target_dept_with_city_anchor():
    extraction = ProjectExtraction(
        is_relevant=True,
        name="Amazon warehouse",
        city="Lyon",
        department="77 - Seine-et-Marne",
    )
    resolved, kind = resolve_extraction_department(
        extraction,
        target_department_code="77",
        country="FR",
    )
    assert kind == "cross_department"
    assert resolved.department == "69 - Rhône"


def test_resolve_keeps_target_when_city_in_target():
    extraction = ProjectExtraction(
        is_relevant=True,
        name="Local plant",
        city="Meaux",
        department=None,
    )
    resolved, kind = resolve_extraction_department(
        extraction,
        target_department_code="77",
        country="FR",
    )
    assert kind == "ok"
    assert resolved.department == "77 - Seine-et-Marne"


def test_resolve_foreign_location():
    extraction = ProjectExtraction(
        is_relevant=True,
        name="LivsMed facility",
        city="Yongin",
        department="77 - Seine-et-Marne",
        address="South Korea",
    )
    resolved, kind = resolve_extraction_department(
        extraction,
        target_department_code="77",
        country="FR",
    )
    assert kind == "foreign"
    assert resolved is extraction
