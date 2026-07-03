"""Tests pour les ancres géographiques (top villes par région)."""
from app.data.search_anchors_loader import (
    anchor_cities_phrase,
    anchor_for_region,
    anchors_for_codes,
    cities_for_region,
)


def test_cities_for_region_rhone():
    cities = cities_for_region("69", "FR")
    assert cities[0] == "Lyon"
    assert "Villeurbanne" in cities
    assert len(cities) == 5


def test_anchor_for_region_germany():
    cities = cities_for_region("NW", "DE")
    assert "Köln" in cities
    assert "Düsseldorf" in cities


def test_anchor_cities_phrase():
    phrase = anchor_cities_phrase("75", "FR")
    assert phrase == "Paris"


def test_anchor_segment_empty_for_global_search():
    from app.data.search_anchors_loader import anchor_segment_for_cities

    assert anchor_segment_for_cities([], "FR") == ""
    assert anchor_segment_for_cities(["Lyon", "Villeurbanne"], "FR") == (
        " autour de Lyon et Villeurbanne"
    )


def test_anchors_for_codes_filters_invalid():
    result = anchors_for_codes(["69", "XX", "38"], "FR")
    assert set(result) == {"69", "38"}
    assert result["69"]["cities"][0] == "Lyon"


def test_anchor_for_region_unknown():
    assert anchor_for_region("99", "FR") is None
