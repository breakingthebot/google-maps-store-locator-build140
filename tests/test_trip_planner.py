# tests/test_trip_planner.py
# Integration tests for TripPlannerService coordinating repository, TSP optimizer, and routing legs.
# Connects to: src/services/trip_planner.py, src/models/trip.py, src/services/store_repository.py
# Created: 2026-09-06

import pytest
from src.models.directions import TravelMode
from src.models.trip import TripPlanRequest
from src.services.mock_maps import MockGoogleMapsService
from src.services.store_repository import StoreRepository
from src.services.trip_planner import TripPlannerService


@pytest.fixture
def planner_service(repo: StoreRepository) -> TripPlannerService:
    mock_maps = MockGoogleMapsService()
    return TripPlannerService(store_repo=repo, maps_service=mock_maps)


@pytest.mark.asyncio
async def test_plan_trip_round_trip_success(planner_service: TripPlannerService) -> None:
    req = TripPlanRequest(
        origin="San Francisco, CA",
        store_ids=[1, 2, 3],
        round_trip=True,
        optimize=True,
        travel_mode=TravelMode.DRIVING,
    )
    result = await planner_service.plan_trip(req)

    assert result.round_trip is True
    assert result.optimized is True
    assert len(result.stops) == 5  # Origin + 3 stores + Return to origin
    assert len(result.legs) == 4   # 4 navigation legs
    assert result.total_distance_km > 0
    assert result.total_distance_miles > 0
    assert len(result.overview_polyline) > 0
    assert result.stops[0].is_origin is True
    assert result.stops[-1].is_destination is True


@pytest.mark.asyncio
async def test_plan_trip_one_way_success(planner_service: TripPlannerService) -> None:
    req = TripPlanRequest(
        origin="37.7749,-122.4194",
        store_ids=[1, 2],
        round_trip=False,
        optimize=False,
        travel_mode=TravelMode.WALKING,
    )
    result = await planner_service.plan_trip(req)

    assert result.round_trip is False
    assert result.optimized is False
    assert len(result.stops) == 3  # Origin + 2 stores
    assert len(result.legs) == 2
    assert result.travel_mode == TravelMode.WALKING


@pytest.mark.asyncio
async def test_plan_trip_requires_minimum_two_stores(planner_service: TripPlannerService) -> None:
    req = TripPlanRequest(
        origin="San Francisco, CA",
        store_ids=[1, 2],
    )
    # Mutate to 1 store to test service validation
    req.store_ids = [1]
    with pytest.raises(ValueError, match="at least 2 store destinations"):
        await planner_service.plan_trip(req)


@pytest.mark.asyncio
async def test_plan_trip_nonexistent_store(planner_service: TripPlannerService) -> None:
    req = TripPlanRequest(
        origin="San Francisco, CA",
        store_ids=[1, 999999],
    )
    with pytest.raises(ValueError, match="Store with ID 999999 not found"):
        await planner_service.plan_trip(req)
