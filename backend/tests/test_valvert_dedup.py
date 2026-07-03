from unittest.mock import AsyncMock, patch

import pytest

from app.agent.dedup_agent import (
    FUZZY_AUTO_MERGE,
    FUZZY_CANDIDATE_MIN,
    find_candidate_pairs,
    has_brand_overlap,
    name_similarity,
    run_dedup_pass,
)
from app.models.project import Project
from app.models.run import Run

VALVERT_NAMES = [
    "Valvert Croix-Blanche",
    "Valvert Croix Blanche",
    "Valvert",
    "Central Park Valvert",
]
CITY = "Décines-Charpieu"


def test_valvert_hyphen_vs_space_auto_merge():
    score = name_similarity("Valvert Croix-Blanche", "Valvert Croix Blanche")
    assert score >= FUZZY_AUTO_MERGE


def test_valvert_short_name_has_brand_overlap_with_variants():
    assert has_brand_overlap("Valvert", "Valvert Croix-Blanche")
    assert has_brand_overlap("Valvert", "Central Park Valvert")
    assert has_brand_overlap("Valvert Croix-Blanche", "Central Park Valvert")


def test_valvert_short_name_in_llm_band_with_brand_overlap():
    score = name_similarity("Valvert", "Valvert Croix-Blanche")
    assert score >= FUZZY_CANDIDATE_MIN
    assert score < FUZZY_AUTO_MERGE
    assert has_brand_overlap("Valvert", "Valvert Croix-Blanche")


def test_valvert_variants_are_candidate_pairs():
    projects = [
        Project(name=name, city=CITY, department="69 - Rhône", match_key=f"k{i}")
        for i, name in enumerate(VALVERT_NAMES)
    ]
    pairs = find_candidate_pairs(projects)
    pair_names = {(pair[0].name, pair[1].name) for pair in pairs}
    assert ("Valvert", "Valvert Croix-Blanche") in pair_names or (
        "Valvert Croix-Blanche",
        "Valvert",
    ) in pair_names
    assert ("Valvert", "Central Park Valvert") in pair_names or (
        "Central Park Valvert",
        "Valvert",
    ) in pair_names


@pytest.mark.asyncio
async def test_run_dedup_pass_merges_valvert_variants_via_llm(db_session):
    run = Run(status="in_progress")
    projects = [
        Project(name=name, city=CITY, department="69 - Rhône", match_key=f"k{i}")
        for i, name in enumerate(VALVERT_NAMES)
    ]
    db_session.add(run)
    db_session.add_all(projects)
    db_session.commit()

    llm_mock = AsyncMock(return_value=(True, ""))
    with patch("app.agent.dedup_agent.ask_llm_same_project", llm_mock):
        events = await run_dedup_pass(db_session, run, ["69"])

    assert len(events) >= 3
    assert llm_mock.call_count >= 2
    survivors = (
        db_session.query(Project)
        .filter(Project.department == "69 - Rhône", Project.merged_into_id.is_(None))
        .count()
    )
    assert survivors == 1
