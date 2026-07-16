"""Ancres géographiques pour les requêtes Exa (top villes / métropole par région)."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.data.departments import _normalize_code, regions_for_country

_DATA_DIR = Path(__file__).resolve().parent / "search_anchors"


@lru_cache
def _load_anchors(country: str) -> dict[str, dict]:
    path = _DATA_DIR / f"{country.lower()}.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def anchor_for_region(code: str, country: str = "FR") -> dict | None:
    normalized = _normalize_code(code.strip(), country)
    return _load_anchors(country.upper()).get(normalized)


def cities_for_region(code: str, country: str = "FR") -> list[str]:
    anchor = anchor_for_region(code, country)
    if not anchor:
        return []
    return list(anchor.get("cities") or [])


def metro_for_region(code: str, country: str = "FR") -> str | None:
    anchor = anchor_for_region(code, country)
    if not anchor:
        return None
    metro = anchor.get("metro")
    return metro if isinstance(metro, str) and metro.strip() else None


def _joiner_for_country(country: str) -> str:
    if country == "DE":
        return " und "
    if country in ("GB", "IE"):
        return " and "
    return " et "


def _phrase_cities(cities: list[str], country: str) -> str:
    if not cities:
        return ""
    if len(cities) == 1:
        return cities[0]
    joiner = _joiner_for_country(country.upper())
    if len(cities) == 2:
        return f"{cities[0]}{joiner}{cities[1]}"
    sep = ", "
    return sep.join(cities[:-1]) + joiner + cities[-1]


def anchor_segment_for_cities(cities: list[str], country: str = "FR") -> str:
    """Suffixe requête Exa ; chaîne vide = recherche département globale."""
    phrase = _phrase_cities(cities, country.upper())
    if not phrase:
        return ""
    normalized = country.upper()
    if normalized == "DE":
        return f" in {phrase}"
    if normalized in ("GB", "IE"):
        return f" around {phrase}"
    return f" autour de {phrase}"


def anchor_cities_phrase(code: str, country: str = "FR") -> str:
    """Phrase naturelle pour les top villes d'une région."""
    return _phrase_cities(cities_for_region(code, country), country.upper())


def anchors_for_country(country: str = "FR") -> dict[str, dict]:
    raw = _load_anchors(country.upper())
    return {
        code: {
            "code": code,
            "metro": entry.get("metro"),
            "cities": list(entry.get("cities") or []),
        }
        for code, entry in raw.items()
    }


def anchors_for_codes(codes: list[str], country: str = "FR") -> dict[str, dict]:
    country = country.upper()
    valid = set(regions_for_country(country))
    result: dict[str, dict] = {}
    for raw in codes:
        code = _normalize_code(raw.strip(), country)
        if code not in valid:
            continue
        anchor = anchor_for_region(code, country)
        if anchor:
            result[code] = {
                "code": code,
                "metro": anchor.get("metro"),
                "cities": list(anchor.get("cities") or []),
            }
    return result
