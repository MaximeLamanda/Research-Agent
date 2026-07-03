"""Recalcule match_key et fusionne les collisions existantes."""

from __future__ import annotations

import asyncio
from collections import defaultdict

from app.agent.dedup_agent import run_dedup_pass
from app.agent.deduplication import make_match_key, merge_projects
from app.data.departments import ensure_department, format_department
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import _migrate_schema
from app.models import ProjectMerge  # noqa: F401
from app.models.project import Project
from app.models.run import Run


def rematch_projects(*, run_fuzzy: bool = True) -> None:
    Base.metadata.create_all(bind=engine)
    _migrate_schema()

    session = SessionLocal()
    try:
        projects = session.query(Project).filter(Project.merged_into_id.is_(None)).all()
        departments_normalized = 0
        for project in projects:
            normalized = ensure_department(project.department)
            if normalized and project.department != normalized:
                project.department = normalized
                departments_normalized += 1
        session.commit()
        print(f"Normalized {departments_normalized} department label(s).")

        projects = session.query(Project).filter(Project.merged_into_id.is_(None)).all()
        groups: dict[str, list[Project]] = defaultdict(list)

        for project in projects:
            new_key = make_match_key(project.name, project.city, project.company)
            groups[new_key].append(project)

        merged = 0
        keys_updated = 0
        for match_key, grouped in groups.items():
            if len(grouped) < 2:
                project = grouped[0]
                if project.match_key != match_key:
                    project.match_key = match_key
                    keys_updated += 1
                continue

            grouped.sort(key=lambda item: item.first_seen_at)
            kept = grouped[0]
            kept.match_key = match_key
            for absorbed in grouped[1:]:
                merge_projects(
                    session,
                    kept,
                    absorbed,
                    run_id=None,
                    method="match_key",
                )
                merged += 1
            session.commit()

        session.commit()
        print(f"Updated {keys_updated} match_key(s).")
        print(f"Merged {merged} project(s) by match_key.")

        if run_fuzzy:
            run = Run(status="completed")
            session.add(run)
            session.commit()
            department_codes = sorted(
                {
                    label.split(" - ", 1)[0]
                    for label in (
                        ensure_department(row[0])
                        for row in session.query(Project.department)
                        .filter(Project.merged_into_id.is_(None), Project.department.isnot(None))
                        .distinct()
                    )
                    if label
                }
            )
            events = asyncio.run(run_dedup_pass(session, run, department_codes))
            session.commit()
            print(f"Fuzzy/LLM pass merged {len(events)} additional project(s).")
            for event in events:
                print(f"  - {event['absorbed_name']} → {event['kept_name']} ({event['method']})")
    finally:
        session.close()


if __name__ == "__main__":
    rematch_projects()
