import uuid
from datetime import date

import pytest

from app.agent.deduplication import (
    _normalize_delivery_date,
    make_match_key,
    merge_people,
    merge_projects,
    upsert_project,
)
from app.agent.schemas import PersonSchema, ProjectExtraction


def test_normalize_delivery_date_keeps_text():
    assert _normalize_delivery_date("Mitte 2028") == "Mitte 2028"
    assert _normalize_delivery_date("juin 2026") == "juin 2026"
    assert _normalize_delivery_date(date(2026, 6, 15)) == "2026-06-15"
    assert _normalize_delivery_date(None) is None


def test_upsert_stores_text_delivery_date(db_session):
    extraction = ProjectExtraction(
        name="Zalando Logistikzentrum",
        city="Gießen",
        company="Zalando",
        is_relevant=True,
        delivery_date="Juni 2026",
    )
    project, is_new = upsert_project(
        db_session,
        extraction,
        url="https://example.com/zalando",
        title="Zalando Gießen",
        raw_excerpt="Inbetriebnahme im Juni",
        run_id=uuid.uuid4(),
    )
    db_session.commit()
    assert is_new is True
    assert project.delivery_date == "Juni 2026"


def test_make_match_key():
    key = make_match_key("Entrepôt XYZ", "Lyon", "LogiFrance")
    assert key == "unknown|lyon"


def test_make_match_key_ignores_company_and_prefixes():
    key_a = make_match_key("Méga-entrepôt Amazon Colombier-Saugnieu", "Colombier-Saugnieu", "Amazon")
    key_b = make_match_key("Entrepôt Amazon Colombier-Saugnieu", "Colombier-Saugnieu", "Amazon France")
    assert key_a == key_b
    assert "amazon" in key_a
    assert "colombier" in key_a


def test_make_match_key_different_projects():
    key_a = make_match_key("Entrepôt frigorifique Alderan", "Satolas-et-Bonce", "Alderan")
    key_b = make_match_key("Entrepôt frigorifique Activimmo", "Satolas-et-Bonce", "Activimmo")
    assert key_a != key_b


def test_merge_people():
    existing = [{"name": "Jean Dupont", "role": "MOA"}]
    new = [{"name": "Marie Martin", "role": "Architecte"}]
    merged = merge_people(existing, new)
    assert len(merged) == 2


def test_upsert_creates_new_project(db_session):
    extraction = ProjectExtraction(
        name="Entrepôt Nord",
        city="Lyon",
        company="LogiFrance",
        is_relevant=True,
        people=[PersonSchema(name="Jean Dupont", role="Chef de projet")],
    )
    project, is_new = upsert_project(
        db_session,
        extraction,
        url="https://example.com/article-1",
        title="Article 1",
        raw_excerpt="excerpt",
        run_id=__import__("uuid").uuid4(),
    )
    db_session.commit()
    assert is_new is True
    assert project.name == "Entrepôt Nord"
    assert len(project.people) == 1


def test_upsert_updates_existing_and_merges_people(db_session):
    import uuid

    from app.models.project_update import ProjectUpdate

    run_id = uuid.uuid4()
    extraction = ProjectExtraction(name="Entrepôt Nord", city="Lyon", company="LogiFrance", is_relevant=True)
    upsert_project(
        db_session,
        extraction,
        url="https://example.com/article-1",
        title="Article 1",
        raw_excerpt="excerpt",
        run_id=run_id,
    )
    db_session.commit()

    extraction2 = ProjectExtraction(
        name="Entrepôt Nord",
        city="Lyon",
        company="LogiFrance",
        is_relevant=True,
        status="travaux",
        people=[PersonSchema(name="Marie Martin", role="Architecte")],
    )
    project, is_new = upsert_project(
        db_session,
        extraction2,
        url="https://example.com/article-2",
        title="Article 2",
        raw_excerpt="excerpt 2",
        run_id=run_id,
    )
    db_session.commit()
    assert is_new is False
    assert project.status == "travaux"
    assert len(project.people) == 1

    updates = db_session.query(ProjectUpdate).all()
    assert len(updates) == 1
    assert updates[0].source.url == "https://example.com/article-2"
    fields = {change["field"] for change in updates[0].changes}
    assert "status" in fields
    assert "people" in fields


def test_upsert_stores_published_at(db_session):
    from datetime import date

    extraction = ProjectExtraction(
        name="Entrepôt Sud",
        city="Marseille",
        is_relevant=True,
    )
    project, is_new = upsert_project(
        db_session,
        extraction,
        url="https://example.com/article-published",
        title="Article publié",
        raw_excerpt="excerpt",
        run_id=uuid.uuid4(),
        published_at=date(2025, 3, 24),
    )
    db_session.commit()
    assert is_new is True
    source = project.sources[0]
    assert source.published_at == date(2025, 3, 24)
    assert source.extracted_data["published_at"] == "2025-03-24"


def test_upsert_reuses_kept_project_when_match_key_was_merged(db_session):
    from app.models.project import Project

    run_id = uuid.uuid4()
    match_key = make_match_key("Garbe Industrial Park Kupferzell", "Kupferzell", "Garbe Industrial")
    kept = Project(
        name="Garbe Industrial Park Kupferzell",
        city="Kupferzell",
        match_key="garbe|industrial|park|kupferzell",
    )
    absorbed = Project(
        name="Garbe Industrial Park Kupferzell",
        city="Kupferzell",
        match_key=match_key,
    )
    db_session.add_all([kept, absorbed])
    db_session.flush()
    absorbed.merged_into_id = kept.id
    db_session.commit()

    extraction = ProjectExtraction(
        name="Garbe Industrial Park Kupferzell",
        city="Kupferzell",
        company="Garbe Industrial",
        is_relevant=True,
        status="travaux",
        sector="logistique",
    )
    project, is_new = upsert_project(
        db_session,
        extraction,
        url="https://www.garbe-industrial.de/richtfest/",
        title="Richtfest Kupferzell",
        raw_excerpt="excerpt",
        run_id=run_id,
        country="DE",
    )
    db_session.commit()

    assert is_new is False
    assert project.id == kept.id
    assert len(kept.sources) == 1


def test_merge_projects_moves_sources_and_marks_absorbed(db_session):
    from app.models.project import Project
    from app.models.project_merge import ProjectMerge
    from app.models.source import Source

    run_id = uuid.uuid4()
    kept = Project(name="Entrepôt Amazon Colombier-Saugnieu", city="Colombier-Saugnieu", match_key="a|b")
    absorbed = Project(name="Méga-entrepôt Amazon Colombier-Saugnieu", city="Colombier-Saugnieu", match_key="c|d")
    db_session.add_all([kept, absorbed])
    db_session.flush()

    db_session.add(
        Source(
            project_id=kept.id,
            url="https://example.com/a",
            title="A",
            run_id=run_id,
        )
    )
    db_session.add(
        Source(
            project_id=absorbed.id,
            url="https://example.com/b",
            title="B",
            run_id=run_id,
        )
    )
    db_session.commit()

    merge = merge_projects(
        db_session,
        kept,
        absorbed,
        run_id=run_id,
        method="fuzzy",
        score=0.95,
    )
    db_session.commit()

    assert absorbed.merged_into_id == kept.id
    assert len(kept.sources) == 2
    assert merge.method == "fuzzy"
    assert db_session.query(ProjectMerge).count() == 1
    assert "changes" in merge.snapshot
    assert "sources_transferred" in merge.snapshot
    assert len(merge.snapshot["sources_transferred"]) == 1
