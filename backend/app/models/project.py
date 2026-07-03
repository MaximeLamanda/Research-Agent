import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy import JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.project_merge import ProjectMerge
    from app.models.project_update import ProjectUpdate
    from app.models.source import Source


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    company: Mapped[str | None] = mapped_column(String)
    siren: Mapped[str | None] = mapped_column(String)
    company_legal_name: Mapped[str | None] = mapped_column(String)
    naf_code: Mapped[str | None] = mapped_column(String)
    surface_m2: Mapped[Decimal | None] = mapped_column(Numeric)
    delivery_date: Mapped[str | None] = mapped_column(String)
    city: Mapped[str | None] = mapped_column(String)
    address: Mapped[str | None] = mapped_column(String)
    department: Mapped[str | None] = mapped_column(String)
    country: Mapped[str | None] = mapped_column(String)
    status: Mapped[str | None] = mapped_column(String)
    sector: Mapped[str | None] = mapped_column(String)
    people: Mapped[list] = mapped_column(JSON, default=list)
    lead_pitch: Mapped[str | None] = mapped_column(String)
    match_key: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    merged_into_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("projects.id"), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    sources: Mapped[list["Source"]] = relationship("Source", back_populates="project")
    merges_as_kept: Mapped[list["ProjectMerge"]] = relationship(
        "ProjectMerge",
        foreign_keys="ProjectMerge.kept_project_id",
        back_populates="kept_project",
    )
    merges_as_absorbed: Mapped[list["ProjectMerge"]] = relationship(
        "ProjectMerge",
        foreign_keys="ProjectMerge.absorbed_project_id",
        back_populates="absorbed_project",
    )
    updates: Mapped[list["ProjectUpdate"]] = relationship("ProjectUpdate", back_populates="project")
