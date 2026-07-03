import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.run import Run


class DedupDecision(Base):
    """Verdict LLM persistant pour une paire de projets (évite de re-poser la même question)."""

    __tablename__ = "dedup_decisions"
    __table_args__ = (
        UniqueConstraint("project_a_id", "project_b_id", name="uq_dedup_decisions_pair"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Paire canonique : project_a_id < project_b_id (ordre str(uuid)).
    project_a_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("projects.id"), nullable=False)
    project_b_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("projects.id"), nullable=False)
    same_project: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str | None] = mapped_column(String)
    # Empreinte des champs pertinents des deux fiches au moment du verdict ;
    # si l'une des fiches change, l'empreinte diverge et le verdict est re-demandé.
    pair_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("runs.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped["Run | None"] = relationship("Run")
