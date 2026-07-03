"""Sandbox : recherche Exa Rhône avec includeDomains + analyse URLs déjà en base."""
from __future__ import annotations

import asyncio
import os
import sys
from collections import Counter
from urllib.parse import urlparse

from dotenv import load_dotenv
from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session, sessionmaker

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.agent.exa_client import ExaClient
from app.agent.known_urls import load_known_urls
from app.agent.queries import SECTOR_QUERIES_FR
from app.config import settings
from app.models.source import Source

RHONE_CODE = "69"
RHONE_LOCAL_DOMAINS = [
    "leprogres.fr",
    "lyoncapitale.fr",
    "lyonmag.com",
    "brefeco.com",
    "lechodutriangle.com",
]

SECTORS = ("logistique", "industriel", "retail")


def _domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _build_query(sector: str) -> str:
    template = SECTOR_QUERIES_FR[sector]
    return template.format(
        dept=RHONE_CODE,
        dept_code=RHONE_CODE,
        dept_label="69 - Rhône",
        dept_name="Rhône",
    ) + " Lyon Villeurbanne Saint-Priest Corbas"


def _db_session() -> Session:
    database_url = os.environ.get("DATABASE_URL", settings.database_url)
    engine = create_engine(database_url)
    return sessionmaker(bind=engine)()


def _rhone_sources_stats(session: Session) -> dict:
    rhone_sources = (
        session.query(Source)
        .filter(Source.url.isnot(None))
        .filter(
            (Source.url.ilike("%leprogres%"))
            | (Source.url.ilike("%lyoncapitale%"))
            | (Source.url.ilike("%lyonmag%"))
            | (Source.url.ilike("%brefeco%"))
            | (Source.url.ilike("%lechodutriangle%"))
        )
        .all()
    )
    all_domains = Counter(_domain(row.url) for row in session.query(Source.url).all())
    return {
        "rhone_local_press_sources": len(rhone_sources),
        "top_domains_in_base": all_domains.most_common(15),
    }


async def run_search(
    exa: ExaClient,
    *,
    label: str,
    query: str,
    include_domains: list[str] | None,
) -> list[dict]:
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"  query: {query[:120]}…")
    if include_domains:
        print(f"  includeDomains: {', '.join(include_domains)}")
    print(f"{'=' * 60}")
    results = await exa.search(
        query,
        num_results=10,
        category="news",
        include_domains=include_domains,
        user_location="FR",
    )
    print(f"  → {len(results)} résultat(s)")
    for i, r in enumerate(results, 1):
        title = (r.get("title") or "")[:70]
        print(f"  {i:2}. [{_domain(r['url'])}] {title}")
    return results


def analyze_results(
    label: str,
    results: list[dict],
    known_urls: set[str],
) -> dict:
    urls = [r["url"] for r in results if r.get("url")]
    known = [u for u in urls if u in known_urls]
    new_urls = [u for u in urls if u not in known_urls]
    domains = Counter(_domain(u) for u in urls)

    print(f"\n--- Analyse {label} ---")
    print(f"  URLs totales      : {len(urls)}")
    print(f"  Déjà en base      : {len(known)} ({100 * len(known) / len(urls):.0f}%)" if urls else "  Déjà en base      : 0")
    print(f"  Nouvelles         : {len(new_urls)}")
    if domains:
        print("  Domaines retournés:")
        for dom, count in domains.most_common():
            print(f"    - {dom}: {count}")
    if known:
        print("  URLs déjà connues:")
        for u in known:
            print(f"    ✓ {u}")
    if new_urls:
        print("  URLs nouvelles:")
        for u in new_urls:
            print(f"    + {u}")

    return {
        "label": label,
        "total": len(urls),
        "known": len(known),
        "new": len(new_urls),
        "known_urls": known,
        "new_urls": new_urls,
        "domains": dict(domains),
    }


async def main() -> int:
    if not settings.exa_api_key:
        print("ÉCHEC : EXA_API_KEY manquante dans .env")
        return 1

    session = _db_session()
    known_urls = load_known_urls(session)
    total_sources = session.query(func.count(Source.id)).scalar() or 0
    base_stats = _rhone_sources_stats(session)

    print("=== Contexte base de données ===")
    print(f"  DATABASE_URL      : {os.environ.get('DATABASE_URL', settings.database_url)}")
    print(f"  URLs connues      : {len(known_urls)} (sources + processed)")
    print(f"  Sources totales   : {total_sources}")
    print(f"  Sources presse locale Rhône déjà en base : {base_stats['rhone_local_press_sources']}")
    print("  Top domaines en base :")
    for dom, count in base_stats["top_domains_in_base"]:
        print(f"    - {dom}: {count}")

    exa = ExaClient(settings.exa_api_key)
    summaries: list[dict] = []

    for sector in SECTORS:
        query = _build_query(sector)

        baseline = await run_search(
            exa,
            label=f"BASELINE — {sector} (sans includeDomains)",
            query=query,
            include_domains=None,
        )
        summaries.append(analyze_results(f"baseline/{sector}", baseline, known_urls))

        local = await run_search(
            exa,
            label=f"LOCAL — {sector} (includeDomains presse Rhône)",
            query=query,
            include_domains=RHONE_LOCAL_DOMAINS,
        )
        summaries.append(analyze_results(f"local/{sector}", local, known_urls))

    print(f"\n{'=' * 60}")
    print("  RÉCAPITULATIF")
    print(f"{'=' * 60}")
    print(f"  {'Recherche':<25} {'Total':>6} {'Connues':>8} {'Nouvelles':>10}")
    for s in summaries:
        print(f"  {s['label']:<25} {s['total']:>6} {s['known']:>8} {s['new']:>10}")

    session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
