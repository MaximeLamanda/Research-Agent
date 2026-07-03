import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.processed_url import ProcessedUrl
    from app.models.project_merge import ProjectMerge
    from app.models.project_update import ProjectUpdate
    from app.models.run_step import RunStep
    from app.models.source import Source


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    articles_found: Mapped[int] = mapped_column(Integer, default=0)
    projects_new: Mapped[int] = mapped_column(Integer, default=0)
    projects_updated: Mapped[int] = mapped_column(Integer, default=0)
    projects_merged: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    mode: Mapped[str] = mapped_column(String, nullable=False, default="full")
    geographical_granularity: Mapped[str] = mapped_column(
        String, nullable=False, default="large"
    )
    exa_search_type: Mapped[str] = mapped_column(String, nullable=False, default="auto")
    exa_category: Mapped[str] = mapped_column(String, nullable=False, default="news")

    sources: Mapped[list["Source"]] = relationship("Source", back_populates="run")
    merges: Mapped[list["ProjectMerge"]] = relationship("ProjectMerge", back_populates="run")
    updates: Mapped[list["ProjectUpdate"]] = relationship("ProjectUpdate", back_populates="run")
    steps: Mapped[list["RunStep"]] = relationship("RunStep", back_populates="run", order_by="RunStep.created_at")
    processed_urls: Mapped[list["ProcessedUrl"]] = relationship("ProcessedUrl", back_populates="run")
