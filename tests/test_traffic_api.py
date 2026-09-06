# tests/test_traffic_api.py
# Integration tests for FastAPI traffic routes and predictive departure endpoints
# Connects to: src/api/routes.py, src/services/traffic_engine.py
# Created: 2026-09-06

import pytest
import httpx


@pytest.mark.asyncio
async def test_directions_with_departure_time(client: httpx.AsyncClient):
    """Test directions endpoint computes traffic delay when given a rush hour departure."""
    res = await client.get(
        "/api/directions",
        params={
            "origin_lat": 37.774929,
            "origin_lng": -122.419416,
            "destination_store_id": 1,
            "mode": "driving",
            "departure_time": "evening_rush",
            "traffic_model": "pessimistic",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["traffic_condition"] is not None
    assert data["duration_in_traffic_seconds"] is not None
    assert data["duration_in_traffic_seconds"] > data["total_duration_seconds"]
    assert data["traffic_delay_seconds"] > 0
    assert len(data["traffic_segments"]) > 0


@pytest.mark.asyncio
async def test_directions_off_peak_traffic(client: httpx.AsyncClient):
    """Test off-peak directions have minimal traffic delay."""
    res = await client.get(
        "/api/directions",
        params={
            "origin_lat": 37.774929,
            "origin_lng": -122.419416,
            "destination_store_id": 1,
            "mode": "driving",
            "departure_time": "off_peak",
            "traffic_model": "optimistic",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["traffic_condition"] == "clear"
    assert data["traffic_delay_seconds"] <= 60


@pytest.mark.asyncio
async def test_trip_plan_with_traffic(client: httpx.AsyncClient):
    """Test trip planner accounts for rush hour congestion across legs."""
    payload = {
        "origin": "37.774929,-122.419416",
        "store_ids": [1, 2, 3],
        "round_trip": False,
        "optimize": True,
        "travel_mode": "driving",
        "departure_time": "morning_rush",
        "traffic_model": "best_guess",
    }
    res = await client.post("/api/trip/plan", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["traffic_condition"] is not None
    assert data["total_traffic_delay_seconds"] > 0
    assert data["total_duration_in_traffic_seconds"] > data["total_duration_seconds"]
    assert len(data["legs"]) == 3
    # Check that legs have traffic segments
    assert any(len(leg.get("traffic_segments", [])) > 0 for leg in data["legs"])


@pytest.mark.asyncio
async def test_traffic_predict_single_destination(client: httpx.AsyncClient):
    """Test predictive departure matrix for a single destination."""
    res = await client.get(
        "/api/traffic/predict",
        params={
            "origin": "37.774929,-122.419416",
            "destination_store_id": 1,
            "travel_mode": "driving",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["predictions"]) == 5
    assert data["best_window"] is not None
    assert data["worst_window"] is not None
    assert data["max_time_saved_seconds"] >= 0


@pytest.mark.asyncio
async def test_traffic_predict_multi_stop(client: httpx.AsyncClient):
    """Test predictive departure matrix for a multi-stop itinerary."""
    res = await client.get(
        "/api/traffic/predict",
        params={
            "origin": "37.774929,-122.419416",
            "store_ids": "1,2,3",
            "travel_mode": "driving",
            "round_trip": "true",
            "optimize": "true",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["predictions"]) == 5
    assert data["best_window"]["window_key"] in ("early_morning", "midday", "off_peak", "night")


@pytest.mark.asyncio
async def test_traffic_overlay_endpoint(client: httpx.AsyncClient):
    """Test arterial traffic overlay endpoint."""
    res = await client.get("/api/traffic/overlay")
    assert res.status_code == 200
    data = res.json()
    assert "arterials" in data
    assert len(data["arterials"]) >= 5
    first = data["arterials"][0]
    assert "name" in first
    assert "color_hex" in first
    assert "condition" in first
