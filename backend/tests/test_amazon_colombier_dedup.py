"""Tests reproduisant le cas Amazon Colombier-Saugnieu (données réelles en base)."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.dedup_agent import (
    FUZZY_AUTO_MERGE,
    FUZZY_CANDIDATE_MIN,
    find_candidate_pairs,
    name_similarity,
    run_dedup_pass,
)
from app.agent.deduplication import extract_name_tokens, make_match_key
from app.models.project import Project
from app.models.run import Run

# Noms et métadonnées issus de research.db après rematch
AMAZON_MEGA = "Méga-entrepôt Amazon Colombier-Saugnieu"
AMAZON_CENTRE = "Centre de distribution Amazon Colombier-Saugnieu"
AMAZON_SHORT = "Amazon Colombier-Saugnieu"
CITY = "Colombier-Saugnieu"


def test_amazon_legacy_rhone_label_normalizes_to_formatted_department():
    from app.data.departments import normalize_department

    assert normalize_department("Rhône") == "69 - Rhône"


def test_amazon_centre_and_mega_share_match_key():
    mega_tokens = extract_name_tokens(AMAZON_MEGA)
    centre_tokens = extract_name_tokens(AMAZON_CENTRE)

    assert "amazon" in mega_tokens and "amazon" in centre_tokens
    assert "centre" in centre_tokens
    assert "distribution" in centre_tokens
    assert make_match_key(AMAZON_MEGA, CITY) == make_match_key(AMAZON_CENTRE, CITY)


def test_amazon_mega_vs_centre_fuzzy_score_in_llm_band_not_auto():
    score = name_similarity(AMAZON_MEGA, AMAZON_CENTRE)

    assert score >= FUZZY_CANDIDATE_MIN
    assert score < FUZZY_AUTO_MERGE
    assert 0.68 <= score <= 0.75


def test_amazon_mega_vs_short_name_shares_match_key_and_candidate_score():
    score = name_similarity(AMAZON_MEGA, AMAZON_SHORT)

    assert score >= FUZZY_CANDIDATE_MIN
    assert make_match_key(AMAZON_MEGA, CITY) == make_match_key(AMAZON_SHORT, CITY)


def test_amazon_mega_vs_centre_is_candidate_pair_when_same_department():
    mega = Project(name=AMAZON_MEGA, city=CITY, department="69 - Rhône", match_key="a")
    centre = Project(name=AMAZON_CENTRE, city=CITY, department="69 - Rhône", match_key="b")

    pairs = find_candidate_pairs([mega, centre])

    assert len(pairs) == 1
    score = pairs[0][2]
    assert FUZZY_CANDIDATE_MIN <= score < FUZZY_AUTO_MERGE


def test_amazon_mega_vs_centre_skipped_when_different_departments_in_db():
    """Cause principale en prod : dept 'Rhône' vs '69' → jamais comparés."""
    mega = Project(name=AMAZON_MEGA, city=CITY, department="69 - Rhône", match_key="a")
    centre = Project(name=AMAZON_CENTRE, city=CITY, department="69", match_key="b")

    pairs_rhone = find_candidate_pairs([mega])
    pairs_69 = find_candidate_pairs([centre])

    assert pairs_rhone == []
    assert pairs_69 == []


@pytest.mark.asyncio
async def test_run_dedup_pass_does_not_call_llm_for_amazon_cross_department(db_session):
    run = Run(status="in_progress")
    mega = Project(
        name=AMAZON_MEGA,
        city=CITY,
        department="69 - Rhône",
        match_key="mega",
    )
    centre = Project(
        name=AMAZON_CENTRE,
        city=CITY,
        department="38 - Isère",
        match_key="centre",
    )
    db_session.add_all([run, mega, centre])
    db_session.commit()

    llm_mock = AsyncMock(return_value=(True, ""))
    with patch("app.agent.dedup_agent.ask_llm_same_project", llm_mock):
        events = await run_dedup_pass(db_session, run, ["69", "38"])

    assert events == []
    llm_mock.assert_not_called()


@pytest.mark.asyncio
async def test_run_dedup_pass_calls_llm_for_amazon_when_same_department_without_company(db_session):
    """Sans promoteur renseigné, le score ~0.69 reste sous le seuil auto → LLM."""
    run = Run(status="in_progress")
    mega = Project(
        name=AMAZON_MEGA,
        city=CITY,
        department="69 - Rhône",
        match_key="mega",
    )
    centre = Project(
        name=AMAZON_CENTRE,
        city=CITY,
        department="69 - Rhône",
        match_key="centre",
    )
    db_session.add_all([run, mega, centre])
    db_session.commit()

    llm_mock = AsyncMock(return_value=(True, ""))
    with patch("app.agent.dedup_agent.ask_llm_same_project", llm_mock):
        events = await run_dedup_pass(db_session, run, ["69"])

    assert len(events) == 1
    assert events[0]["method"] == "llm"
    llm_mock.assert_called_once()
    db_session.refresh(centre)
    assert centre.merged_into_id == mega.id


@pytest.mark.asyncio
async def test_run_dedup_pass_auto_merges_amazon_mega_and_short_same_department(db_session):
    run = Run(status="in_progress")
    mega = Project(
        name=AMAZON_MEGA,
        company="Amazon",
        city=CITY,
        department="69 - Rhône",
        match_key=make_match_key(AMAZON_MEGA, CITY),
    )
    short = Project(
        name=AMAZON_SHORT,
        company="Amazon",
        city=CITY,
        department="69 - Rhône",
        match_key="old-key",
    )
    db_session.add_all([run, mega, short])
    db_session.commit()

    llm_mock = AsyncMock(return_value=False)
    with patch("app.agent.dedup_agent.ask_llm_same_project", llm_mock):
        events = await run_dedup_pass(db_session, run, ["69"])

    assert len(events) == 1
    assert events[0]["method"] == "fuzzy"
    llm_mock.assert_not_called()
    db_session.refresh(short)
    assert short.merged_into_id == mega.id


@pytest.mark.asyncio
async def test_run_dedup_pass_auto_merges_amazon_mega_and_centre_with_company(db_session):
    run = Run(status="in_progress")
    mega = Project(
        name=AMAZON_MEGA,
        company="Amazon",
        city=CITY,
        department="69 - Rhône",
        match_key="mega",
    )
    centre = Project(
        name=AMAZON_CENTRE,
        company="Amazon",
        city=CITY,
        department="69 - Rhône",
        match_key="centre",
    )
    db_session.add_all([run, mega, centre])
    db_session.commit()

    llm_mock = AsyncMock(return_value=False)
    with patch("app.agent.dedup_agent.ask_llm_same_project", llm_mock):
        events = await run_dedup_pass(db_session, run, ["69"])

    assert len(events) == 1
    assert events[0]["method"] == "fuzzy"
    llm_mock.assert_not_called()
    db_session.refresh(centre)
    assert centre.merged_into_id == mega.id
