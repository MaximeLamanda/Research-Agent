from sqlalchemy.orm import Session

from app.data.departments import infer_country_from_department
from app.models.config import Config
from app.models.project import Project


def backfill_project_countries(session: Session, *, default_country: str | None = None) -> int:
    if default_country is None:
        config = session.get(Config, 1)
        default_country = (config.country if config else None) or "FR"

    projects = (
        session.query(Project)
        .filter((Project.country.is_(None)) | (Project.country == ""))
        .all()
    )

    updated = 0
    for project in projects:
        project.country = infer_country_from_department(project.department) or default_country
        updated += 1

    if updated:
        session.commit()

    return updated
