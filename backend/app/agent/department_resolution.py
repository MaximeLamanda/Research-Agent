"""Résolution du département extrait : ville-ancre, détection étranger, cross-dept."""
from __future__ import annotations

import re
import unicodedata
from typing import Literal

from app.agent.schemas import ProjectExtraction
from app.data.departments import ensure_department, format_department, normalize_department
from app.data.search_anchors_loader import anchors_for_country

ResolutionKind = Literal["ok", "cross_department", "foreign"]

_COUNTRY_MARKERS: dict[str, re.Pattern[str]] = {
    "FR": re.compile(r"\b(france|français|francais|île-de-france|ile-de-france)\b", re.IGNORECASE),
    "DE": re.compile(r"\b(germany|deutschland)\b", re.IGNORECASE),
    "GB": re.compile(
        r"\b(united\s+kingdom|\buk\b|england|scotland|wales|northern\s+ireland)\b",
        re.IGNORECASE,
    ),
    "IE": re.compile(r"\b(ireland|éire|eire)\b", re.IGNORECASE),
}

_FOREIGN_BY_TARGET: dict[str, re.Pattern[str]] = {
    "FR": re.compile(
        r"\b(germany|deutschland|united\s+kingdom|\buk\b|ireland|sweden|china|korea|japan)\b",
        re.IGNORECASE,
    ),
    "DE": re.compile(
        r"\b(france|united\s+kingdom|\buk\b|ireland|sweden|china|korea|japan)\b",
        re.IGNORECASE,
    ),
    "GB": re.compile(
        r"\b(france|germany|deutschland|ireland|sweden|china|korea|japan)\b",
        re.IGNORECASE,
    ),
    "IE": re.compile(
        r"\b(france|germany|deutschland|united\s+kingdom|\buk\b|sweden|china|korea|japan)\b",
        re.IGNORECASE,
    ),
}


def _normalize_city(value: str) -> str:
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return text.lower().strip()


def _city_to_department_map(country: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for code, entry in anchors_for_country(country).items():
        for city in entry.get("cities") or []:
            mapping[_normalize_city(city)] = code
    return mapping


def department_from_anchor_city(city: str | None, country: str = "FR") -> str | None:
    if not city or not city.strip():
        return None
    return _city_to_department_map(country).get(_normalize_city(city))


def is_foreign_location(
    city: str | None,
    address: str | None,
    article_text: str,
    *,
    country: str = "FR",
) -> bool:
    blob = " ".join(filter(None, [city, address, article_text[:500] if article_text else ""]))
    if not blob.strip():
        return False
    normalized = country.upper()
    home = _COUNTRY_MARKERS.get(normalized)
    if home and home.search(blob):
        return False
    foreign = _FOREIGN_BY_TARGET.get(normalized)
    if foreign is None:
        return False
    return bool(foreign.search(blob))


def resolve_extraction_department(
    extraction: ProjectExtraction,
    *,
    target_department_code: str,
    country: str = "FR",
) -> tuple[ProjectExtraction, ResolutionKind]:
    if is_foreign_location(extraction.city, extraction.address, "", country=country):
        return extraction, "foreign"

    target_department = format_department(target_department_code, country)
    city_dept_code = department_from_anchor_city(extraction.city, country)

    if city_dept_code:
        city_department = format_department(city_dept_code, country)
        if city_department and city_department != target_department:
            extraction.department = city_department
            return extraction, "cross_department"
        if city_department:
            extraction.department = city_department
            return extraction, "ok"

    extracted_department = normalize_department(extraction.department, country)
    if (
        extracted_department
        and target_department
        and extracted_department != target_department
    ):
        extraction.department = extracted_department
        return extraction, "cross_department"

    extraction.department = ensure_department(
        extraction.department, target_department_code, country
    )
    return extraction, "ok"
