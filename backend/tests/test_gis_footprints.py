from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.gis.constants import AGRICULTURAL_LANDUSE_TAGS
from app.gis.queries import parse_department_code, qualified_table
from app.gis.service import AgriculturalFootprintStats, count_agricultural_footprints
from app.main import app


def test_parse_department_code_from_number():
    assert parse_department_code("33") == "33"
    assert parse_department_code("33 - Gironde") == "33"
    assert parse_department_code("69 - Rhône") == "69"


def test_parse_department_code_invalid():
    with pytest.raises(ValueError):
        parse_department_code("Gironde")


def test_qualified_table_default():
    assert qualified_table("", "public.osm_building_footprints") == '"public"."osm_building_footprints"'


@patch("app.gis.service._gis_engine")
def test_count_agricultural_footprints(mock_engine):
    connection = MagicMock()
    mock_engine.return_value.connect.return_value.__enter__.return_value = connection
    connection.execute.side_effect = [
        MagicMock(scalar_one=lambda: 42),
        MagicMock(all=lambda: [MagicMock(landuse="farmland", count=30), MagicMock(landuse="farmyard", count=12)]),
    ]

    stats = count_agricultural_footprints("33 - Gironde", min_footprint_m2=400)

    assert stats == AgriculturalFootprintStats(
        department_code="33",
        min_footprint_m2=400.0,
        total=42,
        by_landuse={"farmland": 30, "farmyard": 12},
        filter_by_department=True,
    )
    assert connection.execute.call_count == 2


def test_gis_api_requires_department():
    client = TestClient(app)
    response = client.get("/api/gis/agricultural-footprints")
    assert response.status_code == 422


@patch("app.api.gis.count_agricultural_footprints")
def test_gis_api_returns_stats(mock_count):
    mock_count.return_value = AgriculturalFootprintStats(
        department_code="33",
        min_footprint_m2=400.0,
        total=7,
        by_landuse={"farmland": 5, "vineyard": 2},
        filter_by_department=True,
    )
    client = TestClient(app)
    response = client.get("/api/gis/agricultural-footprints?department=33")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 7
    assert payload["department_code"] == "33"
    assert payload["agricultural_landuse_tags"] == list(AGRICULTURAL_LANDUSE_TAGS)


@patch("app.api.gis.count_agricultural_footprints")
def test_gis_api_not_configured(mock_count):
    from app.gis.service import GisDatabaseNotConfiguredError

    mock_count.side_effect = GisDatabaseNotConfiguredError("GIS_DATABASE_URL manquant")
    client = TestClient(app)
    response = client.get("/api/gis/agricultural-footprints?department=33")
    assert response.status_code == 503
