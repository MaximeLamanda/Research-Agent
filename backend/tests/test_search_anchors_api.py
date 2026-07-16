from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_search_anchors_rhone():
    response = client.get("/api/search-anchors", params={"country": "FR", "codes": ["69"]})
    assert response.status_code == 200
    data = response.json()
    assert "69" in data
    assert data["69"]["cities"][0] == "Lyon"
    assert len(data["69"]["cities"]) == 5


def test_search_anchors_germany_land():
    response = client.get("/api/search-anchors", params={"country": "DE", "codes": ["NW"]})
    assert response.status_code == 200
    assert "Köln" in response.json()["NW"]["cities"]


def test_search_anchors_gb_london():
    response = client.get("/api/search-anchors", params={"country": "GB", "codes": ["UKI"]})
    assert response.status_code == 200
    assert response.json()["UKI"]["cities"][0] == "London"


def test_search_anchors_ie_leinster():
    response = client.get("/api/search-anchors", params={"country": "IE", "codes": ["LE"]})
    assert response.status_code == 200
    assert "Dublin" in response.json()["LE"]["cities"]
