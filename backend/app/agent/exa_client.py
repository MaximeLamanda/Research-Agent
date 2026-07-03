from datetime import date, datetime

import httpx

EXA_BASE_URL = "https://api.exa.ai"


def parse_exa_published_date(value: str | None) -> date | None:
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        if "T" in raw:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def published_dates_by_url(*result_lists: list[dict]) -> dict[str, date]:
    dates: dict[str, date] = {}
    for results in result_lists:
        for item in results:
            url = item.get("url")
            if not url:
                continue
            parsed = parse_exa_published_date(item.get("publishedDate"))
            if parsed:
                dates[url] = parsed
    return dates


class ExaClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }

    async def search(
        self,
        query: str,
        num_results: int = 10,
        search_type: str = "auto",
        category: str | None = None,
        start_published_date: str | None = None,
        end_published_date: str | None = None,
        user_location: str | None = "FR",
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
    ) -> list[dict]:
        payload: dict = {
            "query": query,
            "numResults": num_results,
            "type": search_type,
            "contents": {"highlights": {"maxCharacters": 2000}},
        }
        if user_location:
            payload["userLocation"] = user_location
        if category:
            payload["category"] = category
        if start_published_date:
            payload["startPublishedDate"] = start_published_date
        if end_published_date:
            payload["endPublishedDate"] = end_published_date
        if include_domains:
            payload["includeDomains"] = include_domains
        if exclude_domains:
            payload["excludeDomains"] = exclude_domains

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{EXA_BASE_URL}/search",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            return response.json().get("results", [])

    async def fetch(self, urls: list[str], max_characters: int = 8000) -> list[dict]:
        if not urls:
            return []
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{EXA_BASE_URL}/contents",
                headers=self._headers(),
                json={
                    "urls": urls,
                    "text": {"maxCharacters": max_characters},
                },
            )
            response.raise_for_status()
            return response.json().get("results", [])
