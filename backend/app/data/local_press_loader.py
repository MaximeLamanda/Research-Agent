"""Domaines de presse locale par département / Land pour les recherches Exa city_focus."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.data.departments import _normalize_code

_DATA_DIR = Path(__file__).resolve().parent / "local_press_domains"


@lru_cache
def _load_domains(country: str) -> dict[str, list[str]]:
    path = _DATA_DIR / f"{country.lower()}.json"
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, list[str]] = {}
    for code, domains in raw.items():
        normalized = _normalize_code(str(code), country.upper())
        if not isinstance(domains, list):
            continue
        cleaned = []
        seen: set[str] = set()
        for domain in domains:
            if not isinstance(domain, str):
                continue
            d = domain.strip().lower()
            if d and d not in seen:
                seen.add(d)
                cleaned.append(d)
        if cleaned:
            result[normalized] = cleaned
    return result


def local_press_domains_for_department(code: str, country: str = "FR") -> list[str]:
    """Domaines presse locale pour un département ; liste vide si non configuré."""
    normalized = _normalize_code(code.strip(), country.upper())
    return list(_load_domains(country.upper()).get(normalized, []))
