# tests/test_trip_api.py
# API route tests for /api/trip/plan and /api/trip/preview endpoints.
# Connects to: src/api/routes.py, src/models/trip.py
# Created: 2026-09-06

from fastapi.testclient import TestClient
from src.api.app import app

client = TestClient(app)


def test_post_trip_plan_valid() -> None:
    payload = {
        "origin": "San Francisco, CA",
        "store_ids": [1, 2, 4],
        "round_trip": True,
        "optimize": True,
        "travel_mode": "driving",
    }
    response = client.post("/api/trip/plan", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["round_trip"] is True
    assert data["optimized"] is True
    assert len(data["stops"]) == 5  # Origin + 3 stores + Return
    assert len(data["legs"]) == 4
    assert data["total_distance_miles"] > 0
    assert "overview_polyline" in data


def test_post_trip_plan_invalid_store_id() -> None:
    payload = {
        "origin": "San Francisco, CA",
        "store_ids": [1, 888888],
        "round_trip": True,
    }
    response = client.post("/api/trip/plan", json=payload)
    assert response.status_code == 400
    assert "888888 not found" in response.json()["detail"]


def test_post_trip_plan_insufficient_stores() -> None:
    payload = {
        "origin": "San Francisco, CA",
        "store_ids": [1],
    }
    response = client.post("/api/trip/plan", json=payload)
    # Pydantic min_length=2 triggers 422
    assert response.status_code == 422


def test_get_trip_preview_valid() -> None:
    response = client.get("/api/trip/preview?origin=Market%20St&stores=1,2,3&round_trip=false")
    assert response.status_code == 200
    data = response.json()
    assert data["round_trip"] is False
    assert len(data["stops"]) == 4  # Origin + 3 stores (no return)


def test_get_trip_preview_invalid_ids() -> None:
    response = client.get("/api/trip/preview?origin=Market%20St&stores=abc,xyz")
    assert response.status_code == 400
    assert "comma-separated list of integers" in response.json()["detail"]
