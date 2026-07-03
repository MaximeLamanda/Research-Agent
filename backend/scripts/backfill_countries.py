"""Renseigne project.country à partir du département ou de la config."""

from __future__ import annotations

from app.data.project_backfill import backfill_project_countries
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import _migrate_schema


def main() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate_schema()

    session = SessionLocal()
    try:
        updated = backfill_project_countries(session)
        print(f"Backfilled country for {updated} project(s).")
    finally:
        session.close()


if __name__ == "__main__":
    main()
