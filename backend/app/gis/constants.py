"""Constantes pour les requêtes SIG (PostGIS externe)."""

DEFAULT_BUILDINGS_TABLE = "public.osm_building_footprints"
DEFAULT_LANDUSE_TABLE = "public.osm_landuse_areas"

# Tags OSM landuse=* considérés comme usage agricole.
AGRICULTURAL_LANDUSE_TAGS = (
    "farmland",
    "farmyard",
    "meadow",
    "orchard",
    "vineyard",
)

DEFAULT_MIN_FOOTPRINT_M2 = 400.0
