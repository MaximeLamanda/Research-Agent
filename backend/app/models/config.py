from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Config(Base):
    __tablename__ = "config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    country: Mapped[str] = mapped_column(String, nullable=False, default="FR")
    departments: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    region_cities: Mapped[dict[str, list[str]]] = mapped_column(
        JSON, nullable=False, default=lambda: {}
    )
    cron_day: Mapped[int] = mapped_column(Integer, default=0)
    cron_hour: Mapped[int] = mapped_column(Integer, default=6)
    sectors: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: ["industriel", "logistique", "retail"],
    )
    exa_search_type: Mapped[str] = mapped_column(String, nullable=False, default="auto")
    exa_category: Mapped[str] = mapped_column(String, nullable=False, default="news")
    geographical_granularity: Mapped[str] = mapped_column(
        String, nullable=False, default="large"
    )
    exa_published_date_preset: Mapped[str | None] = mapped_column(String, nullable=True)
    exa_start_published_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    exa_end_published_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
