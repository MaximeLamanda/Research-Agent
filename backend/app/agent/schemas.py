from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from app.data.departments import normalize_department


class PersonSchema(BaseModel):
    name: str
    role: str | None = None
    company: str | None = None


class CompanyResolution(BaseModel):
    matched: bool = False
    siren: str | None = None
    company_legal_name: str | None = None
    naf_code: str | None = None
    confidence: Literal["high", "medium", "low"] | None = None
    reason: str | None = None


class ProjectExtraction(BaseModel):
    is_relevant: bool = False
    name: str = ""
    company: str | None = None
    surface_m2: float | None = None
    delivery_date: date | str | None = None
    city: str | None = None
    address: str | None = None
    department: str | None = None
    status: Literal["conception", "travaux", "livraison"] | None = None
    sector: Literal["industriel", "logistique", "retail"] | None = None
    people: list[PersonSchema] = Field(default_factory=list)
    lead_pitch: str | None = None

    @field_validator("department", mode="before")
    @classmethod
    def normalize_department_field(
        cls, value: str | None, info: ValidationInfo
    ) -> str | None:
        if value is None:
            return None
        country = (info.context or {}).get("country", "FR")
        return normalize_department(str(value), country) or str(value).strip() or None
