from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


class ConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    country: str
    departments: list[str]
    region_cities: dict[str, list[str]] = Field(default_factory=dict)
    cron_day: int
    cron_hour: int
    sectors: list[str]
    exa_search_type: str
    exa_category: str
    geographical_granularity: str = "large"
    exa_published_date_preset: str | None = None
    exa_start_published_date: date | None = None
    exa_end_published_date: date | None = None
    exa_published_date_effective_start: date | None = None
    exa_published_date_effective_end: date | None = None
    updated_at: datetime | None = None


class ConfigUpdate(BaseModel):
    country: str | None = None
    departments: list[str] | None = None
    region_cities: dict[str, list[str]] | None = None
    cron_day: int | None = None
    cron_hour: int | None = None
    sectors: list[str] | None = None
    exa_search_type: str | None = None
    exa_category: str | None = None
    geographical_granularity: str | None = None
    exa_published_date_preset: str | None = None
    exa_start_published_date: date | None = None
    exa_end_published_date: date | None = None


class RegionAnchorRead(BaseModel):
    code: str
    metro: str | None = None
    cities: list[str] = Field(default_factory=list)


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    url: str
    title: str | None = None
    published_at: date | None = None
    created_at: datetime | None = None
    run_id: str | None = None
    run_started_at: datetime | None = None
    is_relevant: bool | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    company: str | None = None
    siren: str | None = None
    company_legal_name: str | None = None
    naf_code: str | None = None
    surface_m2: Decimal | float | None = None
    delivery_date: str | None = None
    city: str | None = None
    address: str | None = None
    department: str | None = None
    country: str | None = None
    status: str | None = None
    sector: str | None = None
    people: list[dict] = Field(default_factory=list)
    lead_pitch: str | None = None
    first_seen_at: datetime | None = None
    last_updated_at: datetime | None = None
    sources: list[SourceRead] = Field(default_factory=list)

    @field_validator("delivery_date", mode="before")
    @classmethod
    def normalize_delivery_date(cls, value: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, date):
            return value.isoformat()
        text = str(value).strip()
        return text or None

    @field_serializer("surface_m2")
    def serialize_surface(self, value: Decimal | float | None) -> int | None:
        if value is None:
            return None
        return int(value)


class ProjectMergeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str | None = None
    kept_project_id: str
    absorbed_project_id: str
    method: str
    score: float | None = None
    snapshot: dict = Field(default_factory=dict)
    created_at: datetime | None = None


class FieldChangeRead(BaseModel):
    field: str
    old: str | int | None = None
    new: str | int | None = None


class ProjectUpdateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    project_id: str
    project_name: str
    source_id: str
    source_url: str
    source_title: str | None = None
    changes: list[FieldChangeRead] = Field(default_factory=list)
    created_at: datetime | None = None


class AgriculturalFootprintStatsRead(BaseModel):
    department_code: str
    min_footprint_m2: float
    total: int
    by_landuse: dict[str, int] = Field(default_factory=dict)
    filter_by_department: bool
    agricultural_landuse_tags: list[str] = Field(default_factory=list)


class RunCreate(BaseModel):
    mode: Literal["full", "test_single"] = "full"


class RunDedupCreate(BaseModel):
    """Relance la dédup fuzzy/LLM sur les projets actifs en base."""

    scope: Literal["run", "config", "all"] = "run"
    departments: list[str] | None = None
    country: str | None = None


class RunDedupRead(BaseModel):
    run_id: str
    status: Literal["started"]
    scope: str
    targets: list[dict[str, object]] = Field(default_factory=list)


class RunStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    step_type: str
    message: str | None = None
    data: dict = Field(default_factory=dict)
    created_at: datetime | None = None


class RunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    articles_found: int = 0
    projects_new: int = 0
    projects_updated: int = 0
    projects_merged: int = 0
    error_message: str | None = None
    created_at: datetime | None = None
    mode: str = "full"
    geographical_granularity: str = "large"
    exa_search_type: str = "auto"
    exa_category: str = "news"
