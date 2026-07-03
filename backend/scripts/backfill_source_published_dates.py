"""Renseigne source.published_at pour les articles déjà scannés sans date."""

from __future__ import annotations

import argparse

from app.config import settings
from app.data.source_published_date_backfill import backfill_source_published_dates
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import _migrate_schema


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill des dates de publication manquantes sur les sources existantes."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche le bilan sans modifier la base.",
    )
    parser.add_argument(
        "--use-exa",
        action="store_true",
        help="Interroge l'API Exa pour les URLs encore sans date après le scan des run_steps.",
    )
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    _migrate_schema()

    session = SessionLocal()
    try:
        report = backfill_source_published_dates(
            session,
            use_exa=args.use_exa,
            exa_api_key=settings.exa_api_key,
            dry_run=args.dry_run,
        )
    finally:
        session.close()

    mode = "simulation" if args.dry_run else "mise à jour"
    print(f"Backfill source.published_at ({mode})")
    print(f"  Sources sans date au départ : {report.total_missing}")
    print(f"  Depuis extracted_data       : {report.from_extracted_data}")
    print(f"  Depuis run_steps            : {report.from_run_steps}")
    print(f"  Depuis Exa                  : {report.from_exa}")
    print(f"  Toujours sans date          : {report.still_missing}")
    would_update = report.from_extracted_data + report.from_run_steps + report.from_exa
    if args.dry_run:
        print(f"  Sources qui seraient mises à jour : {would_update}")
    else:
        print(f"  Sources mises à jour        : {report.updated}")


if __name__ == "__main__":
    main()
