from datetime import date
from decimal import Decimal

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.dedup_agent import (
    COMPANY_SIMILARITY_MIN,
    FUZZY_AUTO_MERGE,
    PEOPLE_NAME_SIMILARITY_MIN,
    _project_payload,
    company_similarity,
    find_candidate_pairs,
    has_people_overlap,
    name_similarity,
    run_dedup_pass,
)
from app.agent.deduplication import merge_projects
from app.models.project import Project
from app.models.run import Run
from app.models.source import Source


def test_project_payload_includes_all_fields_and_sources(db_session):
    project = Project(
        name="Centre commercial de la Sourderie",
        company="GA Smart Building",
        city="Montigny-le-Bretonneux",
        address="Place Jacques-Cœur",
        department="78 - Yvelines",
        status="conception",
        sector="commerce",
        surface_m2=Decimal("12000"),
        delivery_date="2029-01-01",
        people=[{"name": "Lorrain Merckaert", "role": "Maire"}],
        lead_pitch="Rénovation du centre commercial",
        match_key="test|key",
    )
    db_session.add(project)
    db_session.flush()
    db_session.add(
        Source(
            project_id=project.id,
            url="https://example.com/article",
            title="Article test",
            published_at=date(2025, 10, 1),
            raw_excerpt="Le centre commercial de la Sourderie sera reconstruit.",
        )
    )
    db_session.commit()
    db_session.refresh(project)

    payload = _project_payload(project)

    assert payload["name"] == "Centre commercial de la Sourderie"
    assert payload["company"] == "GA Smart Building"
    assert payload["city"] == "Montigny-le-Bretonneux"
    assert payload["address"] == "Place Jacques-Cœur"
    assert payload["department"] == "78 - Yvelines"
    assert payload["status"] == "conception"
    assert payload["sector"] == "commerce"
    assert payload["surface_m2"] == 12000.0
    assert payload["delivery_date"] == "2029-01-01"
    assert payload["people"] == [{"name": "Lorrain Merckaert", "role": "Maire"}]
    assert payload["lead_pitch"] == "Rénovation du centre commercial"
    assert len(payload["sources"]) == 1
    assert payload["sources"][0]["title"] == "Article test"
    assert payload["sources"][0]["published_at"] == "2025-10-01"
    assert "Sourderie" in payload["sources"][0]["excerpt"]


def test_name_similarity_same_project_variants():
    score = name_similarity(
        "Entrepôt Amazon Colombier-Saugnieu",
        "Méga-entrepôt Amazon Colombier-Saugnieu",
    )
    assert score >= FUZZY_AUTO_MERGE


def test_name_similarity_different_projects():
    score = name_similarity(
        "Entrepôt frigorifique Alderan",
        "Entrepôt frigorifique Activimmo",
    )
    assert score < FUZZY_AUTO_MERGE


def test_company_similarity_fuzzy_variants():
    score = company_similarity("Carrefour Supply Chain", "Carrefour Supply")
    assert score >= COMPANY_SIMILARITY_MIN


def test_company_similarity_different_companies():
    score = company_similarity("Carrefour Supply", "Amazon France Logistique")
    assert score < COMPANY_SIMILARITY_MIN


def test_has_people_overlap_fuzzy_match():
    people_a = [{"name": "Lorrain Merckaert", "role": "Maire"}]
    people_b = [{"name": "L. Merckaert", "role": None}]
    assert has_people_overlap(people_a, people_b) is True


def test_has_people_overlap_no_match():
    people_a = [{"name": "Alice Martin", "role": "Directrice"}]
    people_b = [{"name": "Bob Dupont", "role": "Maire"}]
    assert has_people_overlap(people_a, people_b) is False


def test_has_people_overlap_empty_lists():
    assert has_people_overlap([], [{"name": "Alice"}]) is False
    assert has_people_overlap([{"name": "Alice"}], []) is False


def test_find_candidate_pairs_same_department(db_session):
    project_a = Project(
        name="Entrepôt Amazon Colombier-Saugnieu",
        city="Colombier-Saugnieu",
        department="69 - Rhône",
        match_key="a|b",
    )
    project_b = Project(
        name="Méga-entrepôt Amazon Colombier-Saugnieu",
        city="Colombier-Saugnieu",
        department="69 - Rhône",
        match_key="c|d",
    )
    db_session.add_all([project_a, project_b])
    db_session.commit()

    pairs = find_candidate_pairs([project_a, project_b])
    assert len(pairs) == 1
    assert pairs[0][2] >= FUZZY_AUTO_MERGE


@pytest.mark.asyncio
async def test_run_dedup_pass_auto_merges_high_score_pairs(db_session):
    run = Run(status="in_progress")
    kept = Project(
        name="Entrepôt Amazon Colombier-Saugnieu",
        city="Colombier-Saugnieu",
        department="69 - Rhône",
        match_key="a|b",
    )
    absorbed = Project(
        name="Méga-entrepôt Amazon Colombier-Saugnieu",
        city="Colombier-Saugnieu",
        department="69 - Rhône",
        match_key="c|d",
    )
    db_session.add_all([run, kept, absorbed])
    db_session.commit()

    events = await run_dedup_pass(db_session, run, ["69"])
    db_session.refresh(absorbed)
    db_session.refresh(run)

    assert len(events) == 1
    assert absorbed.merged_into_id == kept.id
    assert run.projects_merged == 1


@pytest.mark.asyncio
async def test_ask_llm_same_project_logs_reason():
    from unittest.mock import MagicMock, patch

    from app.agent.dedup_agent import ask_llm_same_project
    from app.agent.llm_extractor import LLMExtractor

    project_a = Project(name="Projet A", city="Lyon", match_key="a")
    project_b = Project(name="Projet B", city="Lyon", match_key="b")
    logged: list[dict] = []

    async def capture_logger(event: str, data: dict | None = None, duration_ms: int | None = None):
        if event == "llm_dedup_done":
            logged.append(dict(data or {}))

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"same_project": false, "reason": "Surfaces et adresses incompatibles."}',
                }
            }
        ]
    }
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        same_project, reason = await ask_llm_same_project(
            LLMExtractor(api_key="test"),
            project_a,
            project_b,
            step_logger=capture_logger,
        )

    assert same_project is False
    assert reason == "Surfaces et adresses incompatibles."
    assert logged == [
        {
            "project_a": "Projet A",
            "project_b": "Projet B",
            "same_project": False,
            "reason": "Surfaces et adresses incompatibles.",
        }
    ]


@pytest.mark.asyncio
async def test_run_dedup_pass_uses_llm_for_ambiguous_pairs(db_session):
    run = Run(status="in_progress")
    kept = Project(
        name="Entrepôt frigorifique Alderan / Jacky Perrenot",
        city="Satolas-et-Bonce",
        department="69 - Rhône",
        match_key="a|b",
    )
    absorbed = Project(
        name="Entrepôt frigorifique Activimmo/Jacky Perrenot",
        city="Satolas-et-Bonce",
        department="69 - Rhône",
        match_key="c|d",
    )
    db_session.add_all([run, kept, absorbed])
    db_session.commit()

    with patch("app.agent.dedup_agent.ask_llm_same_project", new=AsyncMock(return_value=(True, ""))):
        events = await run_dedup_pass(db_session, run, ["69"])

    db_session.refresh(absorbed)
    assert len(events) == 1
    assert absorbed.merged_into_id == kept.id
    assert events[0]["method"] == "llm"


def test_find_candidate_pairs_same_company_different_city_without_name_match(db_session):
    project_a = Project(
        name="Plateforme XXL Nord Isère",
        company="Carrefour Supply Chain",
        city="Bourgoin-Jallieu",
        department="38 - Isère",
        match_key="a|b",
    )
    project_b = Project(
        name="Site industriel Grand Angle",
        company="Carrefour Supply",
        city="Ruy-Montceau",
        department="38 - Isère",
        match_key="c|d",
    )
    db_session.add_all([project_a, project_b])
    db_session.commit()

    pairs = find_candidate_pairs([project_a, project_b])
    assert len(pairs) == 1


def test_find_candidate_pairs_different_company_no_other_signal(db_session):
    project_a = Project(
        name="Plateforme XXL Nord Isère",
        company="Carrefour Supply",
        city="Bourgoin-Jallieu",
        department="38 - Isère",
        match_key="a|b",
    )
    project_b = Project(
        name="Site industriel Grand Angle",
        company="Amazon France Logistique",
        city="Lyon",
        department="69 - Rhône",
        match_key="c|d",
    )
    db_session.add_all([project_a, project_b])
    db_session.commit()

    pairs = find_candidate_pairs([project_a, project_b])
    assert pairs == []


def test_find_candidate_pairs_shared_contact_different_city_without_name_match(db_session):
    contact = [{"name": "Lorrain Merckaert", "role": "Maire"}]
    project_a = Project(
        name="Rénovation centre Sourderie",
        city="Montigny-le-Bretonneux",
        department="78 - Yvelines",
        people=contact,
        match_key="a|b",
    )
    project_b = Project(
        name="Extension parc activités",
        city="Trappes",
        department="78 - Yvelines",
        people=[{"name": "L. Merckaert", "role": "Élu"}],
        match_key="c|d",
    )
    db_session.add_all([project_a, project_b])
    db_session.commit()

    pairs = find_candidate_pairs([project_a, project_b])
    assert len(pairs) == 1


@pytest.mark.asyncio
async def test_run_dedup_pass_same_company_different_city_goes_to_llm(db_session):
    run = Run(status="in_progress")
    kept = Project(
        name="Plateforme logistique Carrefour Supply",
        company="Carrefour Supply Chain",
        city="Vénissieux",
        department="69 - Rhône",
        match_key="a|b",
    )
    absorbed = Project(
        name="Nouveau hub e-commerce",
        company="Carrefour Supply",
        city="Corbas",
        department="69 - Rhône",
        match_key="c|d",
    )
    db_session.add_all([run, kept, absorbed])
    db_session.commit()

    llm_mock = AsyncMock(return_value=(False, "Deux sites distincts"))
    with patch("app.agent.dedup_agent.ask_llm_same_project", new=llm_mock):
        events = await run_dedup_pass(db_session, run, ["69"])

    assert events == []
    llm_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_dedup_pass_shared_contact_goes_to_llm(db_session):
    run = Run(status="in_progress")
    kept = Project(
        name="Rénovation centre Sourderie",
        city="Montigny-le-Bretonneux",
        department="78 - Yvelines",
        people=[{"name": "Lorrain Merckaert", "role": "Maire"}],
        match_key="a|b",
    )
    absorbed = Project(
        name="Extension parc activités",
        city="Trappes",
        department="78 - Yvelines",
        people=[{"name": "L. Merckaert", "role": "Élu"}],
        match_key="c|d",
    )
    db_session.add_all([run, kept, absorbed])
    db_session.commit()

    llm_mock = AsyncMock(return_value=(True, "Même opération citée par le maire"))
    with patch("app.agent.dedup_agent.ask_llm_same_project", new=llm_mock):
        events = await run_dedup_pass(db_session, run, ["78"])

    assert len(events) == 1
    assert events[0]["method"] == "llm"
    llm_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_dedup_pass_caches_negative_llm_verdict(db_session):
    from app.models import DedupDecision

    run = Run(status="in_progress")
    kept = Project(
        name="Entrepôt frigorifique Alderan / Jacky Perrenot",
        city="Satolas-et-Bonce",
        department="69 - Rhône",
        match_key="a|b",
    )
    absorbed = Project(
        name="Entrepôt frigorifique Activimmo/Jacky Perrenot",
        city="Satolas-et-Bonce",
        department="69 - Rhône",
        match_key="c|d",
    )
    db_session.add_all([run, kept, absorbed])
    db_session.commit()

    llm_mock = AsyncMock(return_value=(False, "Deux opérations distinctes"))
    with patch("app.agent.dedup_agent.ask_llm_same_project", new=llm_mock):
        events_first = await run_dedup_pass(db_session, run, ["69"])
        events_second = await run_dedup_pass(db_session, run, ["69"])

    assert events_first == []
    assert events_second == []
    llm_mock.assert_awaited_once()  # 2nd pass served from cache

    decision = db_session.query(DedupDecision).one()
    assert decision.same_project is False
    assert decision.reason == "Deux opérations distinctes"


@pytest.mark.asyncio
async def test_run_dedup_pass_reasks_llm_when_project_changed(db_session):
    run = Run(status="in_progress")
    kept = Project(
        name="Entrepôt frigorifique Alderan / Jacky Perrenot",
        city="Satolas-et-Bonce",
        department="69 - Rhône",
        match_key="a|b",
    )
    absorbed = Project(
        name="Entrepôt frigorifique Activimmo/Jacky Perrenot",
        city="Satolas-et-Bonce",
        department="69 - Rhône",
        match_key="c|d",
    )
    db_session.add_all([run, kept, absorbed])
    db_session.commit()

    llm_mock = AsyncMock(return_value=(False, ""))
    with patch("app.agent.dedup_agent.ask_llm_same_project", new=llm_mock):
        await run_dedup_pass(db_session, run, ["69"])

        absorbed.address = "ZAC de Chesnes, Satolas-et-Bonce"
        db_session.commit()

        await run_dedup_pass(db_session, run, ["69"])

    assert llm_mock.await_count == 2  # fingerprint changed -> re-ask


@pytest.mark.asyncio
async def test_run_dedup_pass_cached_positive_verdict_merges_without_llm(db_session):
    from app.agent.dedup_agent import store_verdict

    run = Run(status="in_progress")
    kept = Project(
        name="Entrepôt frigorifique Alderan / Jacky Perrenot",
        city="Satolas-et-Bonce",
        department="69 - Rhône",
        match_key="a|b",
    )
    absorbed = Project(
        name="Entrepôt frigorifique Activimmo/Jacky Perrenot",
        city="Satolas-et-Bonce",
        department="69 - Rhône",
        match_key="c|d",
    )
    db_session.add_all([run, kept, absorbed])
    db_session.commit()

    store_verdict(
        db_session, kept, absorbed,
        same_project=True, reason="Même chantier", run_id=run.id,
    )
    db_session.commit()

    llm_mock = AsyncMock(return_value=(False, ""))
    with patch("app.agent.dedup_agent.ask_llm_same_project", new=llm_mock):
        events = await run_dedup_pass(db_session, run, ["69"])

    db_session.refresh(absorbed)
    assert len(events) == 1
    assert events[0]["method"] == "llm_cached"
    assert absorbed.merged_into_id == kept.id
    llm_mock.assert_not_awaited()


def test_store_verdict_handles_concurrent_insert_race(db_session):
    from unittest.mock import MagicMock

    from app.agent.dedup_agent import _pair_key, pair_fingerprint, store_verdict
    from app.models import DedupDecision

    kept = Project(
        name="Entrepôt frigorifique Alderan / Jacky Perrenot",
        city="Satolas-et-Bonce",
        department="69 - Rhône",
        match_key="a|b",
    )
    absorbed = Project(
        name="Entrepôt frigorifique Activimmo/Jacky Perrenot",
        city="Satolas-et-Bonce",
        department="69 - Rhône",
        match_key="c|d",
    )
    db_session.add_all([kept, absorbed])
    db_session.commit()

    # Ligne concurrente déjà en base pour la paire canonique.
    a_id, b_id = _pair_key(kept, absorbed)
    db_session.add(
        DedupDecision(
            project_a_id=a_id,
            project_b_id=b_id,
            same_project=True,
            reason="Verdict concurrent",
            pair_fingerprint="empreinte-perimee",
        )
    )
    db_session.commit()

    # Simule la course : le SELECT initial de store_verdict rate la ligne,
    # l'insert déclenche l'IntegrityError sur la contrainte unique.
    real_query = db_session.query
    state = {"missed": False}

    def query_missing_once(*args, **kwargs):
        if not state["missed"] and args and args[0] is DedupDecision:
            state["missed"] = True
            wrapper = MagicMock()
            wrapper.filter.return_value.first.return_value = None
            return wrapper
        return real_query(*args, **kwargs)

    with patch.object(db_session, "query", side_effect=query_missing_once):
        store_verdict(
            db_session,
            absorbed,  # ordre des arguments inversé volontairement
            kept,
            same_project=False,
            reason="Deux opérations distinctes",
            run_id=None,
        )
    db_session.commit()

    decisions = db_session.query(DedupDecision).all()
    assert len(decisions) == 1
    decision = decisions[0]
    assert decision.same_project is False
    assert decision.reason == "Deux opérations distinctes"
    assert decision.pair_fingerprint == pair_fingerprint(kept, absorbed)
