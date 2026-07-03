from unittest.mock import AsyncMock, patch

import pytest

from app.agent.dedup_agent import (
    ADDRESS_AUTO_MERGE,
    ADDRESS_CANDIDATE_MIN,
    FUZZY_CANDIDATE_MIN,
    address_similarity,
    find_candidate_pairs,
    has_address_overlap,
    name_similarity,
    run_dedup_pass,
)
from app.models.project import Project
from app.models.run import Run

VALVERT_ADDRESS = "Zone commerciale Croix-Blanche, route de Corbeil"
CITY = "Saint-Michel-sur-Orge"
DEPARTMENT = "91 - Essonne"


def test_valvert_vs_generic_name_low_name_similarity():
    score = name_similarity("Valvert Croix-Blanche", "Nouveau centre commercial XXL en Essonne")
    assert score < FUZZY_CANDIDATE_MIN


def test_similar_addresses_detected():
    score = address_similarity(
        VALVERT_ADDRESS,
        "route de Corbeil, zone Croix-Blanche",
    )
    assert score >= ADDRESS_CANDIDATE_MIN
    assert has_address_overlap(VALVERT_ADDRESS, "route de Corbeil, zone Croix-Blanche")


def test_find_candidate_pairs_by_address_despite_different_names():
    project_a = Project(
        name="Valvert Croix-Blanche",
        city=CITY,
        address=VALVERT_ADDRESS,
        department=DEPARTMENT,
        match_key="a",
    )
    project_b = Project(
        name="Nouveau centre commercial XXL en Essonne",
        city=CITY,
        address="route de Corbeil, zone Croix-Blanche",
        department=DEPARTMENT,
        match_key="b",
    )

    pairs = find_candidate_pairs([project_a, project_b])

    assert len(pairs) == 1
    assert name_similarity(project_a.name, project_b.name) < FUZZY_CANDIDATE_MIN
    assert pairs[0][2] >= ADDRESS_CANDIDATE_MIN


def test_unrelated_projects_same_city_not_candidates():
    project_a = Project(
        name="Entrepôt Amazon",
        city="Satolas-et-Bonce",
        address="Zone Activité Nord",
        department="69 - Rhône",
        match_key="a",
    )
    project_b = Project(
        name="Centre commercial Ecully",
        city="Satolas-et-Bonce",
        address="Zone Activité Sud",
        department="69 - Rhône",
        match_key="b",
    )

    pairs = find_candidate_pairs([project_a, project_b])

    assert len(pairs) == 0
    assert not has_address_overlap(project_a.address, project_b.address)


@pytest.mark.asyncio
async def test_run_dedup_pass_merges_valvert_vs_generic_via_llm(db_session):
    run = Run(status="in_progress")
    kept = Project(
        name="Valvert Croix-Blanche",
        city=CITY,
        address=VALVERT_ADDRESS,
        department=DEPARTMENT,
        match_key="a",
    )
    absorbed = Project(
        name="Nouveau centre commercial XXL en Essonne",
        city=CITY,
        address="route de Corbeil, zone Croix-Blanche",
        department=DEPARTMENT,
        match_key="b",
    )
    db_session.add_all([run, kept, absorbed])
    db_session.commit()

    llm_mock = AsyncMock(return_value=True)
    with patch("app.agent.dedup_agent.ask_llm_same_project", llm_mock):
        events = await run_dedup_pass(db_session, run, ["91"])

    db_session.refresh(absorbed)
    assert len(events) == 1
    assert absorbed.merged_into_id is not None
    assert events[0]["method"] in ("llm", "fuzzy")


def test_near_identical_addresses_auto_merge_score():
    score = address_similarity(
        "12 avenue Croix-Blanche, Saint-Michel-sur-Orge",
        "12 avenue Croix-Blanche Saint-Michel-sur-Orge",
    )
    assert score >= ADDRESS_AUTO_MERGE


def test_generic_zone_addresses_not_similar():
    score = address_similarity("Zone Activité Nord", "Zone Activité Sud")
    assert score < ADDRESS_CANDIDATE_MIN
    assert not has_address_overlap("Zone Activité Nord", "Zone Activité Sud")
