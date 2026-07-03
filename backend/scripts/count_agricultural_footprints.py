#!/usr/bin/env python3
"""Compte les emprises OSM > seuil intersectant un landuse agricole."""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.gis.constants import DEFAULT_MIN_FOOTPRINT_M2
from app.gis.service import GisDatabaseNotConfiguredError, count_agricultural_footprints


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Nombre de footprints OSM > seuil m² dans un landuse agricole (PostGIS)."
    )
    parser.add_argument("department", help="Code département, ex. 33 ou « 33 - Gironde »")
    parser.add_argument(
        "--min-m2",
        type=float,
        default=DEFAULT_MIN_FOOTPRINT_M2,
        help=f"Seuil emprise en m² (défaut {DEFAULT_MIN_FOOTPRINT_M2})",
    )
    parser.add_argument(
        "--no-dept-filter",
        action="store_true",
        help="Ne pas filtrer sur code_insee (toute la base chargée)",
    )
    parser.add_argument("--json", action="store_true", help="Sortie JSON")
    args = parser.parse_args()

    try:
        stats = count_agricultural_footprints(
            args.department,
            min_footprint_m2=args.min_m2,
            filter_by_department=not args.no_dept_filter,
        )
    except GisDatabaseNotConfiguredError as exc:
        print(f"Erreur: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"Erreur: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(
            json.dumps(
                {
                    "department_code": stats.department_code,
                    "min_footprint_m2": stats.min_footprint_m2,
                    "total": stats.total,
                    "by_landuse": stats.by_landuse,
                    "filter_by_department": stats.filter_by_department,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    print(f"Département : {stats.department_code}")
    print(f"Seuil       : > {stats.min_footprint_m2:g} m²")
    print(f"Total       : {stats.total}")
    if stats.by_landuse:
        print("Détail landuse :")
        for tag, count in stats.by_landuse.items():
            print(f"  - {tag}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
