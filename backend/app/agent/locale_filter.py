"""Filtres géographiques / linguistiques pour les candidats Exa."""
from __future__ import annotations

import re

_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")
_CJK_TLD_RE = re.compile(r"\.网|网/|网$")
# Pattern typique des fermes SEO (ex. /html/20260706/816124.html).
_SPAM_URL_PATH_RE = re.compile(r"/html/\d{8}/")
_EXA_USER_LOCATION = {
    "FR": "FR",
    "DE": "DE",
    "GB": "GB",
    "IE": "IE",
}


def exa_user_location_for_country(country: str) -> str | None:
    return _EXA_USER_LOCATION.get(country.upper())


def is_likely_foreign_candidate(
    title: str,
    snippet: str,
    url: str,
    *,
    country: str = "FR",
) -> bool:
    """Heuristique rapide : candidat hors pays cible (avant préfiltre LLM)."""
    blob = f"{title} {snippet}"
    if _CJK_RE.search(blob):
        return True
    if _CJK_TLD_RE.search(url):
        return True
    if _SPAM_URL_PATH_RE.search(url):
        return True
    return False
