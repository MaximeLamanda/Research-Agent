from unittest.mock import AsyncMock, patch

import pytest

from app.agent.entreprise_client import EntrepriseClient, extract_dept_code


def test_extract_dept_code():
    assert extract_dept_code("69 - Rhône") == "69"
    assert extract_dept_code("BY - Bayern") is None
    assert extract_dept_code(None) is None


@pytest.mark.asyncio
async def test_search_returns_candidates():
    mock_response = {
        "results": [
            {
                "siren": "552032534",
                "nom_complet": "DANONE",
                "nom_raison_sociale": "DANONE",
                "activite_principale": "10.51C",
                "siege": {
                    "adresse": "17 BOULEVARD HAUSSMANN",
                    "code_postal": "75009",
                    "libelle_commune": "PARIS",
                    "departement": "75",
                },
            }
        ],
        "total_results": 1,
    }

    client = EntrepriseClient()
    with patch.object(client, "_get", new_callable=AsyncMock, return_value=mock_response):
        results = await client.search("Danone", departement="75")

    assert len(results) == 1
    assert results[0].siren == "552032534"
    assert results[0].nom_complet == "DANONE"
    assert results[0].naf_code == "10.51C"
    assert results[0].ville == "PARIS"
