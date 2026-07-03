"""Cas signalés en prod (run 3967a62c / 2ec69ee9) — doublons non fusionnés."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.dedup_agent import (
    FUZZY_AUTO_MERGE,
    find_candidate_pairs,
    name_similarity,
    run_dedup_pass,
)
from app.agent.deduplication import extract_name_tokens, make_match_key
from app.models.project import Project
from app.models.run import Run

AMAZON_EN = "Amazon distribution center Colombier-Saugnieu"
AMAZON_FR = "Méga-entrepôt Amazon Colombier-Saugnieu"
AMAZON_CENTRE = "Centre de distribution Amazon Colombier-Saugnieu"
AMAZON_PITCH = "New Amazon logistics center in Colombier-Saugnieu"
CITY_AMAZON = "Colombier-Saugnieu"

BRON_A = "Extension of Nouvelles Galeries Bron"
BRON_B = "Expansion of Galeries Lafayette in Bron"
CITY_BRON = "Bron"
COMPANY_BRON = "Citynove"

LIDL_A = "Germany's largest Lidl - Rheinfelden"
LIDL_B = "Lidl largest branch Rheinfelden"
CITY_LIDL = "Rheinfelden"
COMPANY_LIDL = "Lidl"


def test_amazon_english_variants_share_match_key():
    assert make_match_key(AMAZON_EN, CITY_AMAZON) == make_match_key(AMAZON_PITCH, CITY_AMAZON)
    assert make_match_key(AMAZON_EN, CITY_AMAZON) == make_match_key(AMAZON_FR, CITY_AMAZON)


def test_amazon_english_variants_auto_merge_score():
    score = name_similarity(AMAZON_EN, AMAZON_PITCH)
    assert score >= FUZZY_AUTO_MERGE


def test_bron_galeries_variants_share_core_tokens():
    tokens_a = extract_name_tokens(BRON_A)
    tokens_b = extract_name_tokens(BRON_B)
    assert "bron" in tokens_a and "bron" in tokens_b
    assert "galerie" in tokens_a and "galerie" in tokens_b


@pytest.mark.asyncio
async def test_run_dedup_pass_auto_merges_bron_galeries_same_company(db_session):
    run = Run(status="in_progress")
    a = Project(
        name=BRON_A,
        company=COMPANY_BRON,
        city=CITY_BRON,
        department="69 — Rhône",
        match_key="legacy-bron-a",
    )
    b = Project(
        name=BRON_B,
        company=COMPANY_BRON,
        city=CITY_BRON,
        department="69 - Rhône",
        match_key="legacy-bron-b",
    )
    db_session.add_all([run, a, b])
    db_session.commit()

    events = await run_dedup_pass(db_session, run, ["69"])

    assert len(events) == 1
    assert events[0]["method"] == "fuzzy"
    db_session.refresh(b)
    assert b.merged_into_id == a.id


@pytest.mark.asyncio
async def test_run_dedup_pass_merges_amazon_variants_with_em_dash_department(db_session):
    run = Run(status="in_progress")
    en = Project(
        name=AMAZON_EN,
        company="Amazon",
        city=CITY_AMAZON,
        department="69 — Rhône",
        match_key=make_match_key(AMAZON_EN, CITY_AMAZON),
    )
    pitch = Project(
        name=AMAZON_PITCH,
        company="Amazon",
        city=CITY_AMAZON,
        department="69 - Rhône",
        match_key="legacy-key",
    )
    db_session.add_all([run, en, pitch])
    db_session.commit()

    events = await run_dedup_pass(db_session, run, ["69"])

    assert len(events) == 1
    db_session.refresh(pitch)
    assert pitch.merged_into_id == en.id


@pytest.mark.asyncio
async def test_run_dedup_pass_merges_lidl_rheinfelden_without_llm(db_session):
    run = Run(status="in_progress")
    a = Project(
        name=LIDL_A,
        company=COMPANY_LIDL,
        city=CITY_LIDL,
        department="BW — Baden-Württemberg",
        match_key="legacy-lidl-a",
    )
    b = Project(
        name=LIDL_B,
        company=COMPANY_LIDL,
        city=CITY_LIDL,
        department="BW - Baden-Württemberg",
        match_key="legacy-lidl-b",
    )
    db_session.add_all([run, a, b])
    db_session.commit()

    llm_mock = AsyncMock(return_value=False)
    with patch("app.agent.dedup_agent.ask_llm_same_project", llm_mock):
        events = await run_dedup_pass(db_session, run, ["BW"], country="DE")

    assert len(events) == 1
    assert events[0]["method"] == "fuzzy"
    llm_mock.assert_not_called()
    db_session.refresh(b)
    assert b.merged_into_id == a.id


def test_amazon_centre_still_candidate_with_mega():
    mega = Project(name=AMAZON_FR, city=CITY_AMAZON, department="69 - Rhône", match_key="a")
    centre = Project(name=AMAZON_CENTRE, city=CITY_AMAZON, department="69 - Rhône", match_key="b")
    pairs = find_candidate_pairs([mega, centre])
    assert len(pairs) == 1


def test_cross_city_generic_overlap_not_candidate():
    """Amazon Gemmingen ↔ Phoenix Neuhausen : logistics/center communs, villes différentes."""
    from app.agent.dedup_agent import has_brand_overlap

    gemmingen = Project(
        name="New Amazon logistics center Gemmingen",
        city="Gemmingen",
        department="BW - Baden-Württemberg",
        match_key="a",
    )
    neuhausen = Project(
        name="Phoenix logistics center Neuhausen",
        city="Neuhausen",
        department="BW - Baden-Württemberg",
        match_key="b",
    )
    assert not has_brand_overlap(gemmingen.name, neuhausen.name)
    assert find_candidate_pairs([gemmingen, neuhausen]) == []


def test_expansion_only_overlap_not_brand_match():
    from app.agent.dedup_agent import has_brand_overlap

    assert not has_brand_overlap(
        "Factory expansion Hummel Denzlingen",
        "Extension of Tripsdrill Cleebronn",
    )


def test_lidl_rheinfelden_same_city_remains_candidate():
    from app.agent.dedup_agent import has_brand_overlap

    a = Project(name=LIDL_A, city=CITY_LIDL, department="BW - Baden-Württemberg", match_key="a")
    b = Project(name=LIDL_B, city=CITY_LIDL, department="BW - Baden-Württemberg", match_key="b")
    assert has_brand_overlap(a.name, b.name)
    pairs = find_candidate_pairs([a, b])
    assert len(pairs) == 1
