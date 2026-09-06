# tests/test_api.py
# Integration tests for FastAPI endpoints: stores, directions, geocoding, and health checks.
# Connects to: src/api/app.py, src/api/routes.py
# Created: 2026-09-06

import pytest
import httpx


@pytest.mark.asyncio
async def test_api_health(client: httpx.AsyncClient):
    """GET /api/health should return 200 with system telemetry."""
    res = await client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["total_stores"] > 0
    assert "version" in data


@pytest.mark.asyncio
async def test_api_config(client: httpx.AsyncClient):
    """GET /api/config should return public configuration."""
    res = await client.get("/api/config")
    assert res.status_code == 200
    data = res.json()
    assert "defaultLat" in data
    assert "defaultLng" in data


@pytest.mark.asyncio
async def test_api_geocode_address(client: httpx.AsyncClient):
    """GET /api/geocode with address query should return coordinates."""
    res = await client.get("/api/geocode?address=San+Francisco")
    assert res.status_code == 200
    data = res.json()
    assert data["coordinates"]["latitude"] == pytest.approx(37.7749, abs=0.01)
    assert data["coordinates"]["longitude"] == pytest.approx(-122.4194, abs=0.01)


@pytest.mark.asyncio
async def test_api_geocode_reverse(client: httpx.AsyncClient):
    """GET /api/geocode with lat/lng coordinates should return formatted address."""
    res = await client.get("/api/geocode?lat=37.7749&lng=-122.4194")
    assert res.status_code == 200
    data = res.json()
    assert "formatted_address" in data


@pytest.mark.asyncio
async def test_api_search_stores(client: httpx.AsyncClient):
    """GET /api/stores should return nearest stores with calculated distance and operating status."""
    res = await client.get("/api/stores?lat=37.7749&lng=-122.4194&radius_km=25")
    assert res.status_code == 200
    data = res.json()
    assert data["total_found"] > 0
    first = data["stores"][0]
    assert "distance_km" in first
    assert "distance_miles" in first
    assert "is_open_now" in first
    assert "store" in first


@pytest.mark.asyncio
async def test_api_search_stores_by_address(client: httpx.AsyncClient):
    """GET /api/stores with address string should geocode and return results."""
    res = await client.get("/api/stores?address=Market+St,+San+Francisco&radius_km=15")
    assert res.status_code == 200
    data = res.json()
    assert data["total_found"] > 0


@pytest.mark.asyncio
async def test_api_search_stores_endpoint_alias(client: httpx.AsyncClient):
    """GET /api/stores/search should resolve without 422 integer parsing collision."""
    res = await client.get("/api/stores/search?lat=37.7749&lng=-122.4194&radius_km=25")
    assert res.status_code == 200
    data = res.json()
    assert data["total_found"] > 0



@pytest.mark.asyncio
async def test_api_get_store_detail(client: httpx.AsyncClient):
    """GET /api/stores/{id} should return complete store profile."""
    res = await client.get("/api/stores/1")
    assert res.status_code == 200
    store = res.json()
    assert store["id"] == 1
    assert "hours" in store
    assert "amenities" in store


@pytest.mark.asyncio
async def test_api_get_store_not_found(client: httpx.AsyncClient):
    """GET /api/stores/{id} with non-existent ID should return 404."""
    res = await client.get("/api/stores/99999")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_api_directions(client: httpx.AsyncClient):
    """GET /api/directions should compute turn-by-turn routing steps and polyline."""
    url = "/api/directions?origin_lat=37.7749&origin_lng=-122.4194&destination_store_id=1&mode=driving"
    res = await client.get(url)
    assert res.status_code == 200
    directions = res.json()
    assert directions["total_distance_km"] > 0
    assert len(directions["steps"]) >= 3
    assert len(directions["overview_polyline"]) > 0


@pytest.mark.asyncio
async def test_api_create_store(client: httpx.AsyncClient):
    """POST /api/stores should register a new store and return 201."""
    payload = {
        "name": "Apex Retail - North Beach",
        "brand": "Apex Retail",
        "street": "550 Columbus Ave",
        "city": "San Francisco",
        "state": "CA",
        "postal_code": "94133",
        "country": "US",
        "latitude": 37.8005,
        "longitude": -122.4101,
        "amenities": {"wifi": True, "curbside_pickup": True},
        "hours": {},
    }
    res = await client.post("/api/stores", json=payload)
    assert res.status_code == 201
    created = res.json()
    assert created["id"] > 0
    assert created["name"] == "Apex Retail - North Beach"


@pytest.mark.asyncio
async def test_api_search_filter_rating(client: httpx.AsyncClient):
    """GET /api/stores/search with rating_45 or min_rating should filter lower rated stores."""
    res = await client.get("/api/stores/search?lat=37.7749&lng=-122.4194&radius_km=30&min_rating=4.6")
    assert res.status_code == 200
    data = res.json()
    assert data["total_found"] > 0
    for s in data["stores"]:
        assert s["store"]["rating"] >= 4.6


@pytest.mark.asyncio
async def test_api_search_filter_amenities(client: httpx.AsyncClient):
    """GET /api/stores/search with drive_thru=true should return only drive-thru equipped stores."""
    res = await client.get("/api/stores/search?lat=37.7749&lng=-122.4194&radius_km=30&drive_thru=true")
    assert res.status_code == 200
    data = res.json()
    assert data["total_found"] > 0
    for s in data["stores"]:
        assert s["store"]["amenities"]["drive_thru"] is True


@pytest.mark.asyncio
async def test_api_search_filter_multiple_amenities(client: httpx.AsyncClient):
    """GET /api/stores/search with multiple amenity flags should apply conjunction (AND) filtering."""
    res = await client.get("/api/stores/search?lat=37.7749&lng=-122.4194&radius_km=30&drive_thru=true&ev_charging=true")
    assert res.status_code == 200
    data = res.json()
    for s in data["stores"]:
        assert s["store"]["amenities"]["drive_thru"] is True
        assert s["store"]["amenities"]["ev_charging"] is True

