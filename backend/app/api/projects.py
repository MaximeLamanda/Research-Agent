import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.data.departments import ensure_department
from app.db.session import get_db
from app.models.project import Project
from app.models.project_merge import ProjectMerge
from app.models.source import Source
from app.api.serializers import source_to_read
from app.schemas import ProjectMergeRead, ProjectRead

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _merge_to_read(merge: ProjectMerge) -> ProjectMergeRead:
    return ProjectMergeRead(
        id=str(merge.id),
        run_id=str(merge.run_id) if merge.run_id else None,
        kept_project_id=str(merge.kept_project_id),
        absorbed_project_id=str(merge.absorbed_project_id),
        method=merge.method,
        score=merge.score,
        snapshot=merge.snapshot or {},
        created_at=merge.created_at,
    )


def _project_to_read(project: Project) -> ProjectRead:
    return ProjectRead(
        id=str(project.id),
        name=project.name,
        company=project.company,
        surface_m2=project.surface_m2,
        delivery_date=project.delivery_date,
        city=project.city,
        address=project.address,
        department=project.department,
        country=project.country,
        status=project.status,
        sector=project.sector,
        people=project.people or [],
        lead_pitch=project.lead_pitch,
        first_seen_at=project.first_seen_at,
        last_updated_at=project.last_updated_at,
        sources=[source_to_read(s) for s in project.sources],
    )


@router.get("", response_model=list[ProjectRead])
def list_projects(
    department: str | None = Query(None),
    status: str | None = Query(None),
    sector: str | None = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Project).options(
        joinedload(Project.sources).joinedload(Source.run)
    )
    if department:
        dept_filter = ensure_department(department, department)
        if dept_filter:
            query = query.filter(Project.department == dept_filter)
    if status:
        query = query.filter(Project.status == status)
    if sector:
        query = query.filter(Project.sector == sector)
    projects = query.filter(Project.merged_into_id.is_(None)).order_by(Project.last_updated_at.desc()).all()
    return [_project_to_read(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: uuid.UUID, db: Session = Depends(get_db)):
    project = (
        db.query(Project)
        .options(joinedload(Project.sources).joinedload(Source.run))
        .filter(Project.id == project_id, Project.merged_into_id.is_(None))
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _project_to_read(project)


@router.get("/{project_id}/merges", response_model=list[ProjectMergeRead])
def list_project_merges(project_id: uuid.UUID, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    merges = (
        db.query(ProjectMerge)
        .filter(
            or_(
                ProjectMerge.kept_project_id == project_id,
                ProjectMerge.absorbed_project_id == project_id,
            )
        )
        .order_by(ProjectMerge.created_at.desc())
        .all()
    )
    return [_merge_to_read(merge) for merge in merges]
