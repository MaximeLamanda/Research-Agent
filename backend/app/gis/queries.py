"""Requêtes PostGIS pour emprises bâtiment × landuse agricole."""

from __future__ import annotations

import re

_IDENT = re.compile(r"^[a-z][a-z0-9_]*$")
_DEPT_CODE = re.compile(r"^(\d{2,3}|[A-Z]{2})$")


def parse_department_code(department: str) -> str:
    """Extrait le code département depuis « 33 », « 33 - Gironde », etc."""
    raw = (department or "").strip()
    if not raw:
        raise ValueError("department requis")

    head = raw.split("-", 1)[0].strip()
    if _DEPT_CODE.match(head):
        return head

    match = re.search(r"\b(\d{2,3}|[A-Z]{2})\b", raw)
    if match:
        return match.group(1)

    raise ValueError(f"code département invalide: {department!r}")


def _parse_qualified_table(raw: str, default: str) -> tuple[str, str]:
    value = (raw or default).strip()
    parts = [part.strip() for part in value.split(".") if part.strip()]
    if len(parts) == 1:
        return "public", parts[0]
    if len(parts) == 2:
        return parts[0], parts[1]
    raise ValueError(f"table qualifiée invalide: {raw!r}")


def _validate_ident(name: str, label: str) -> None:
    if not _IDENT.match(name):
        raise ValueError(f'{label} invalide: "{name}"')


def qualified_table(raw: str, default: str) -> str:
    schema, table = _parse_qualified_table(raw, default)
    _validate_ident(schema, "schéma")
    _validate_ident(table, "table")
    return f'"{schema}"."{table}"'


def count_agricultural_footprints_sql(
    *,
    buildings_table: str,
    landuse_table: str,
    filter_by_department: bool,
) -> str:
    dept_filter = "AND b.code_insee LIKE :dept_prefix\n" if filter_by_department else ""

    return f"""
SELECT COUNT(DISTINCT (b.osm_type, b.osm_id))::bigint AS total
FROM {buildings_table} b
WHERE ST_Area(ST_Transform(b.geom, 2154)) > :min_m2
  {dept_filter}  AND EXISTS (
    SELECT 1
    FROM {landuse_table} lu
    WHERE b.geom && lu.geom
      AND ST_Intersects(b.geom, lu.geom)
      AND lu.landuse IN :landuse_tags
  )
"""


def breakdown_by_landuse_sql(
    *,
    buildings_table: str,
    landuse_table: str,
    filter_by_department: bool,
) -> str:
    dept_filter = "AND b.code_insee LIKE :dept_prefix\n" if filter_by_department else ""

    return f"""
SELECT lu.landuse, COUNT(DISTINCT (b.osm_type, b.osm_id))::bigint AS count
FROM {buildings_table} b
JOIN {landuse_table} lu
  ON b.geom && lu.geom
 AND ST_Intersects(b.geom, lu.geom)
WHERE ST_Area(ST_Transform(b.geom, 2154)) > :min_m2
  {dept_filter}  AND lu.landuse IN :landuse_tags
GROUP BY lu.landuse
ORDER BY count DESC, lu.landuse
"""
