from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.entreprise_client import CompanyCandidate
from app.agent.pipeline import enrich_company
from app.agent.schemas import CompanyResolution, ProjectExtraction


@pytest.mark.asyncio
async def test_enrich_company_applies_resolution():
    extraction = ProjectExtraction(
        is_relevant=True,
        name="Entrepôt Amazon",
        company="Amazon France Logistique",
        city="Colombier-Saugnieu",
        department="69 - Rhône",
    )
    entreprise = MagicMock()
    entreprise.search = AsyncMock(
        return_value=[
            CompanyCandidate(
                siren="123456789",
                nom_complet="AMAZON FRANCE LOGISTIQUE",
                naf_code="52.10B",
                ville="Colombier-Saugnieu",
            )
        ]
    )
    resolver = MagicMock()
    resolver.resolve = AsyncMock(
        return_value=CompanyResolution(
            matched=True,
            siren="123456789",
            company_legal_name="AMAZON FRANCE LOGISTIQUE",
            naf_code="52.10B",
            confidence="high",
            reason="ok",
        )
    )

    result = await enrich_company(
        extraction,
        article_text="Amazon construit un entrepôt...",
        country="FR",
        entreprise=entreprise,
        resolver=resolver,
    )

    assert result.siren == "123456789"
    assert result.company_legal_name == "AMAZON FRANCE LOGISTIQUE"
    entreprise.search.assert_awaited_once()
    resolver.resolve.assert_awaited_once()


@pytest.mark.asyncio
async def test_enrich_company_skips_non_fr():
    extraction = ProjectExtraction(is_relevant=True, name="Halle", company="Firma GmbH")
    result = await enrich_company(extraction, article_text="text", country="DE")
    assert result.matched is False
