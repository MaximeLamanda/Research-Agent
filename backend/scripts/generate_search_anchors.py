"""Génère les fichiers d'ancres géographiques (top villes par dept / Land)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.data.departments import DE_LANDER, FR_DEPARTMENTS

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "app" / "data" / "search_anchors"
TOP_N = 5
GEO_BASE = "https://geo.api.gouv.fr"

# Top villes par Bundesland (population / poids économique) — pas d'API équivalente geo.gouv
DE_TOP_CITIES: dict[str, list[str]] = {
    "BW": ["Stuttgart", "Mannheim", "Karlsruhe", "Freiburg im Breisgau", "Heidelberg"],
    "BY": ["München", "Nürnberg", "Augsburg", "Regensburg", "Ingolstadt"],
    "BE": ["Berlin"],
    "BB": ["Potsdam", "Cottbus", "Brandenburg an der Havel", "Frankfurt (Oder)", "Oranienburg"],
    "HB": ["Bremen", "Bremerhaven"],
    "HH": ["Hamburg"],
    "HE": ["Frankfurt am Main", "Wiesbaden", "Kassel", "Darmstadt", "Offenbach am Main"],
    "MV": ["Rostock", "Schwerin", "Neubrandenburg", "Stralsund", "Greifswald"],
    "NI": ["Hannover", "Braunschweig", "Osnabrück", "Oldenburg", "Wolfsburg"],
    "NW": ["Köln", "Düsseldorf", "Dortmund", "Essen", "Duisburg"],
    "RP": ["Mainz", "Ludwigshafen am Rhein", "Koblenz", "Trier", "Kaiserslautern"],
    "SL": ["Saarbrücken", "Neunkirchen", "Homburg", "Völklingen", "Saarlouis"],
    "SN": ["Dresden", "Leipzig", "Chemnitz", "Zwickau", "Plauen"],
    "ST": ["Magdeburg", "Halle (Saale)", "Dessau-Roßlau", "Wittenberg", "Halberstadt"],
    "SH": ["Kiel", "Lübeck", "Flensburg", "Neumünster", "Norderstedt"],
    "TH": ["Erfurt", "Jena", "Gera", "Weimar", "Gotha"],
}


def _fetch_epci_name(client: httpx.Client, dept_code: str) -> str | None:
    response = client.get(f"{GEO_BASE}/departements/{dept_code}/epcis", timeout=30.0)
    if response.status_code != 200:
        return None
    epcis = response.json()
    if not epcis:
        return None
    # Préférer une métropole si présente
    for epci in epcis:
        nom = epci.get("nom") or ""
        if "Métropole" in nom or "métropole" in nom:
            return nom
    return epcis[0].get("nom")


def _fetch_top_communes(client: httpx.Client, dept_code: str) -> list[str]:
    response = client.get(
        f"{GEO_BASE}/communes",
        params={
            "codeDepartement": dept_code,
            "fields": "nom,population",
            "format": "json",
        },
        timeout=60.0,
    )
    response.raise_for_status()
    communes = response.json()
    ranked = sorted(communes, key=lambda c: c.get("population") or 0, reverse=True)
    return [c["nom"] for c in ranked[:TOP_N] if c.get("nom")]


def generate_fr() -> dict[str, dict]:
    anchors: dict[str, dict] = {}
    with httpx.Client() as client:
        for code in FR_DEPARTMENTS:
            print(f"  FR {code}…", flush=True)
            cities = _fetch_top_communes(client, code)
            metro = _fetch_epci_name(client, code)
            entry: dict = {"cities": cities}
            if metro:
                entry["metro"] = metro
            anchors[code] = entry
    return anchors


def generate_de() -> dict[str, dict]:
    anchors: dict[str, dict] = {}
    for code in DE_LANDER:
        cities = DE_TOP_CITIES.get(code, [])
        anchors[code] = {"cities": cities[:TOP_N]}
    return anchors


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Génération ancres FR (geo.api.gouv.fr)…")
    fr_data = generate_fr()
    fr_path = OUTPUT_DIR / "fr.json"
    fr_path.write_text(json.dumps(fr_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"  → {fr_path} ({len(fr_data)} départements)")

    print("Génération ancres DE…")
    de_data = generate_de()
    de_path = OUTPUT_DIR / "de.json"
    de_path.write_text(json.dumps(de_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"  → {de_path} ({len(de_data)} Länder)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
