"""Smoke test Exa + Vercel AI Gateway (deepseek-v4-flash)."""
import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

sys.path.insert(0, os.path.dirname(__file__))

from app.agent.exa_client import ExaClient
from app.agent.llm_extractor import LLMExtractor
from app.config import settings


async def main():
    print(f"Modèle : {settings.ai_model}")
    print("1. Test Exa search…")
    exa = ExaClient(settings.exa_api_key)
    results = await exa.search(
        "article construction entrepôt logistique département 69 France 2025",
        num_results=2,
    )
    print(f"   → {len(results)} résultats")
    if not results:
        print("ÉCHEC : aucun résultat Exa")
        return 1

    url = results[0]["url"]
    title = results[0].get("title", "")
    print(f"   → {title[:60]}…")

    print("2. Test Exa fetch…")
    fetched = await exa.fetch([url], max_characters=4000)
    text = fetched[0].get("text", "") if fetched else ""
    print(f"   → {len(text)} caractères")
    if len(text) < 100:
        print("ÉCHEC : contenu article trop court")
        return 1

    print("3. Test extraction LLM…")
    llm = LLMExtractor()
    extraction = await llm.extract(text[:3000], title=title)
    print(f"   → Projet : {extraction.name}")
    print(f"   → Ville  : {extraction.city}")
    print(f"   → Statut : {extraction.status}")
    print(f"   → People : {len(extraction.people)}")
    print("\n✅ Smoke test OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
