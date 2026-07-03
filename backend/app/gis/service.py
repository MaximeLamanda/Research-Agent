"""Exécution des requêtes SIG sur une base PostGIS externe."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.engine import Engine

from app.config import settings
from app.gis.constants import (
    AGRICULTURAL_LANDUSE_TAGS,
    DEFAULT_BUILDINGS_TABLE,
    DEFAULT_LANDUSE_TABLE,
    DEFAULT_MIN_FOOTPRINT_M2,
)
from app.gis.queries import (
    breakdown_by_landuse_sql,
    count_agricultural_footprints_sql,
    parse_department_code,
    qualified_table,
)


class GisDatabaseNotConfiguredError(RuntimeError):
    pass


@dataclass(frozen=True)
class AgriculturalFootprintStats:
    department_code: str
    min_footprint_m2: float
    total: int
    by_landuse: dict[str, int]
    filter_by_department: bool


@lru_cache
def _gis_engine() -> Engine:
    url = (settings.gis_database_url or "").strip()
    if not url:
        raise GisDatabaseNotConfiguredError(
            "GIS_DATABASE_URL non configuré (PostGIS externe requis)"
        )
    return create_engine(url, pool_pre_ping=True)


def _build_params(
    *,
    department_code: str,
    min_footprint_m2: float,
    filter_by_department: bool,
) -> dict:
    params: dict = {
        "min_m2": min_footprint_m2,
        "landuse_tags": list(AGRICULTURAL_LANDUSE_TAGS),
    }
    if filter_by_department:
        params["dept_prefix"] = f"{department_code}%"
    return params


def _prepare_statement(sql: str) -> text:
    return text(sql).bindparams(bindparam("landuse_tags", expanding=True))


def count_agricultural_footprints(
    department: str,
    *,
    min_footprint_m2: float = DEFAULT_MIN_FOOTPRINT_M2,
    filter_by_department: bool = True,
) -> AgriculturalFootprintStats:
    department_code = parse_department_code(department)
    buildings = qualified_table(settings.gis_buildings_table, DEFAULT_BUILDINGS_TABLE)
    landuse = qualified_table(settings.gis_landuse_table, DEFAULT_LANDUSE_TABLE)
    params = _build_params(
        department_code=department_code,
        min_footprint_m2=min_footprint_m2,
        filter_by_department=filter_by_department,
    )

    count_sql = count_agricultural_footprints_sql(
        buildings_table=buildings,
        landuse_table=landuse,
        filter_by_department=filter_by_department,
    )
    breakdown_sql = breakdown_by_landuse_sql(
        buildings_table=buildings,
        landuse_table=landuse,
        filter_by_department=filter_by_department,
    )

    engine = _gis_engine()
    with engine.connect() as conn:
        total = conn.execute(_prepare_statement(count_sql), params).scalar_one()
        rows = conn.execute(_prepare_statement(breakdown_sql), params).all()

    return AgriculturalFootprintStats(
        department_code=department_code,
        min_footprint_m2=min_footprint_m2,
        total=int(total or 0),
        by_landuse={str(row.landuse): int(row.count) for row in rows},
        filter_by_department=filter_by_department,
    )
