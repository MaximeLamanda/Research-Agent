from app.data.search_anchors_loader import (
    anchor_segment_for_cities,
    anchors_for_country,
    cities_for_region,
)


def test_gb_london_cities():
    cities = cities_for_region("UKI", "GB")
    assert cities[0] == "London"
    assert len(cities) == 5


def test_ie_leinster_cities():
    cities = cities_for_region("LE", "IE")
    assert "Dublin" in cities
    assert len(cities) == 5


def test_gb_anchor_segment_english():
    segment = anchor_segment_for_cities(["Manchester", "Liverpool"], "GB")
    assert "around" in segment
    assert "and" in segment


def test_all_gb_regions_have_anchors():
    anchors = anchors_for_country("GB")
    assert len(anchors) == 12


def test_all_ie_provinces_have_anchors():
    anchors = anchors_for_country("IE")
    assert len(anchors) == 4
