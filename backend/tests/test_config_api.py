def test_get_and_update_config(client):
    response = client.get("/api/config")
    assert response.status_code == 200
    assert response.json()["exa_start_published_date"] is None
    assert response.json()["exa_end_published_date"] is None
    assert response.json()["exa_published_date_preset"] is None
    assert response.json()["exa_published_date_effective_start"] is None
    assert response.json()["exa_published_date_effective_end"] is None
    assert response.json()["region_cities"] == {}

    response = client.put(
        "/api/config",
        json={"geographical_granularity": "city_focus", "exa_search_type": "deep"},
    )
    assert response.status_code == 200
    assert response.json()["geographical_granularity"] == "large"
    assert response.json()["exa_search_type"] == "auto"

    response = client.put("/api/config", json={"country": "DE", "departments": ["BY", "NW"]})
    assert response.status_code == 200
    assert response.json()["country"] == "DE"
    assert response.json()["departments"] == ["BY", "NW"]

    response = client.put(
        "/api/config",
        json={"country": "GB", "departments": ["UKI", "UKD"]},
    )
    assert response.status_code == 200
    assert response.json()["country"] == "GB"
    assert response.json()["departments"] == ["UKI", "UKD"]

    response = client.put("/api/config", json={"departments": ["69", "01"]})
    assert response.status_code == 200
    assert response.json()["departments"] == ["69", "01"]

    response = client.put(
        "/api/config",
        json={
            "exa_published_date_preset": "custom",
            "exa_start_published_date": "2025-01-01",
            "exa_end_published_date": "2025-12-31",
        },
    )
    assert response.status_code == 200
    assert response.json()["exa_published_date_preset"] == "custom"
    assert response.json()["exa_start_published_date"] == "2025-01-01"
    assert response.json()["exa_end_published_date"] == "2025-12-31"
    assert response.json()["exa_published_date_effective_start"] == "2025-01-01"
    assert response.json()["exa_published_date_effective_end"] == "2025-12-31"

    response = client.put(
        "/api/config",
        json={"exa_published_date_preset": "this_year"},
    )
    assert response.status_code == 200
    assert response.json()["exa_published_date_preset"] == "this_year"
    assert response.json()["exa_published_date_effective_start"] is not None
    assert response.json()["exa_published_date_effective_end"] is not None

    response = client.put(
        "/api/config",
        json={"region_cities": {"69": ["Lyon", "Villeurbanne"]}},
    )
    assert response.status_code == 200
    assert response.json()["region_cities"] == {}
