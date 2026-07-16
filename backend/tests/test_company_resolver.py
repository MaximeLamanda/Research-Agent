import json
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.company_resolver import CompanyResolver
from app.agent.entreprise_client import CompanyCandidate
from app.agent.schemas import CompanyResolution


@pytest.mark.asyncio
async def test_resolve_picks_candidate():
    candidates = [
        CompanyCandidate(
            siren="552032534",
            nom_complet="DANONE",
            naf_code="10.51C",
            ville="PARIS",
        ),
        CompanyCandidate(
            siren="999999999",
            nom_complet="DANONE LOGISTIQUE",
            naf_code="52.10B",
            ville="LYON",
        ),
    ]

    llm_json = json.dumps(
        {
            "matched": True,
            "siren": "552032534",
            "company_legal_name": "DANONE",
            "naf_code": "10.51C",
            "confidence": "high",
            "reason": "Correspond au nom extrait et au contexte article.",
        }
    )

    resolver = CompanyResolver()
    with patch.object(resolver, "_call_llm", new_callable=AsyncMock, return_value=llm_json):
        result = await resolver.resolve(
            company_name="Danone",
            article_context="Danone investit dans un nouvel entrepôt à Paris.",
            candidates=candidates,
            city="Paris",
        )

    assert isinstance(result, CompanyResolution)
    assert result.matched is True
    assert result.siren == "552032534"
    assert result.company_legal_name == "DANONE"


@pytest.mark.asyncio
async def test_resolve_no_candidates():
    resolver = CompanyResolver()
    result = await resolver.resolve(
        company_name="Inconnue",
        article_context="texte",
        candidates=[],
    )
    assert result.matched is False
    assert result.siren is None


@pytest.mark.asyncio
async def test_resolve_handles_invalid_llm_json():
    candidates = [
        CompanyCandidate(
            siren="552032534",
            nom_complet="BUGATTI",
            naf_code="29.10Z",
            ville="DORLISHEIM",
        ),
    ]
    resolver = CompanyResolver()
    with patch.object(
        resolver,
        "_call_llm",
        new_callable=AsyncMock,
        return_value='{"matched": true, "reason": "guillemets "cassés"}',
    ):
        result = await resolver.resolve(
            company_name="Bugatti",
            article_context="Bugatti ouvre une manufacture.",
            candidates=candidates,
        )

    assert result.matched is False
    assert "Réponse LLM invalide" in (result.reason or "")
