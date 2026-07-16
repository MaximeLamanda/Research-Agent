import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.agent.url_prefilter import UrlPrefilter, decisions_from_response


def _candidates():
    return [
        {"url": "https://a.com/1", "title": "Nouvelle usine à Lyon", "snippet": "…", "published_at": "2026-06-01"},
        {"url": "https://a.com/2", "title": "Contournement RN88", "snippet": "…", "published_at": None},
        {"url": "https://a.com/3", "title": "Extension entrepôt", "snippet": "…", "published_at": None},
    ]


def test_decisions_from_response_parses_plain_json():
    content = json.dumps([
        {"url": "https://a.com/1", "fetch": True, "reason": "usine neuve"},
        {"url": "https://a.com/2", "fetch": False, "reason": "voirie"},
    ])
    decisions = decisions_from_response(content)
    assert decisions["https://a.com/1"] == (True, "usine neuve")
    assert decisions["https://a.com/2"] == (False, "voirie")


def test_decisions_from_response_tolerates_wrapped_dict():
    content = json.dumps(
        {"results": [{"url": "https://a.com/1", "fetch": True, "reason": "ok"}]}
    )
    decisions = decisions_from_response(content)
    assert decisions["https://a.com/1"] == (True, "ok")


def test_decisions_from_response_tolerates_single_object():
    content = json.dumps({"url": "https://a.com/1", "fetch": False, "reason": "voirie"})
    decisions = decisions_from_response(content)
    assert decisions["https://a.com/1"] == (False, "voirie")


def test_decisions_from_response_parses_fenced_json():
    content = '```json\n[{"url": "https://a.com/1", "fetch": false, "reason": "hors sujet"}]\n```'
    decisions = decisions_from_response(content)
    assert decisions["https://a.com/1"] == (False, "hors sujet")


@pytest.mark.asyncio
async def test_select_returns_fetch_flags_and_fail_open_for_missing_urls():
    # L'URL 3 est absente de la réponse LLM → fail-open (retenue).
    llm_content = json.dumps([
        {"url": "https://a.com/1", "fetch": True, "reason": "ok"},
        {"url": "https://a.com/2", "fetch": False, "reason": "voirie"},
    ])
    fake_response = MagicMock()
    fake_response.json.return_value = {"choices": [{"message": {"content": llm_content}}]}
    fake_response.raise_for_status = MagicMock()

    prefilter = UrlPrefilter(api_key="k", model="m")
    with patch("app.agent.url_prefilter.httpx.AsyncClient") as client_cls:
        client = client_cls.return_value.__aenter__.return_value
        client.post = AsyncMock(return_value=fake_response)
        decisions = await prefilter.select(_candidates())

    assert decisions["https://a.com/1"] == (True, "ok")
    assert decisions["https://a.com/2"] == (False, "voirie")
    assert decisions["https://a.com/3"][0] is True  # fail-open


@pytest.mark.asyncio
async def test_select_propagates_http_errors():
    prefilter = UrlPrefilter(api_key="k", model="m")
    with patch("app.agent.url_prefilter.httpx.AsyncClient") as client_cls:
        client = client_cls.return_value.__aenter__.return_value
        client.post = AsyncMock(side_effect=httpx.ConnectError("boom"))
        with pytest.raises(httpx.ConnectError):
            await prefilter.select(_candidates())


@pytest.mark.asyncio
async def test_select_with_no_candidates_returns_empty_without_llm_call():
    prefilter = UrlPrefilter(api_key="k", model="m")
    with patch("app.agent.url_prefilter.httpx.AsyncClient") as client_cls:
        decisions = await prefilter.select([])
    assert decisions == {}
    client_cls.assert_not_called()
