# tests/test_store_repository.py
# Unit and integration tests for StoreRepository SQLite operations and spatial queries.
# Connects to: src/services/store_repository.py, src/models/store.py
# Created: 2026-09-06

import pytest
from src.models.store import StoreAmenities, StoreCreate, WeeklyHours
from src.services.store_repository import StoreRepository


def test_repository_seeding(repo: StoreRepository):
    """Repository should auto-seed default flagship retail locations on initialization."""
    stores = repo.list_all()
    assert len(stores) >= 12
    first = stores[0]
    assert first.name
    assert first.street
    assert first.city
    assert first.latitude != 0.0
    assert first.longitude != 0.0


def test_get_by_id(repo: StoreRepository):
    """Retrieve an existing store by its ID."""
    store = repo.get_by_id(1)
    assert store is not None
    assert store.id == 1
    assert "Union Square" in store.name or "Apex" in store.name


def test_get_by_invalid_id(repo: StoreRepository):
    """Requesting non-existent ID should return None."""
    assert repo.get_by_id(99999) is None


def test_add_store(repo: StoreRepository):
    """Insert a new store and verify retrieval."""
    new_store = StoreCreate(
        name="Apex Retail - Test Lab",
        brand="Apex Retail",
        street="100 Innovation Way",
        city="San Jose",
        state="CA",
        postal_code="95110",
        latitude=37.3382,
        longitude=-121.8863,
        amenities=StoreAmenities(drive_thru=True, ev_charging=True),
        hours=WeeklyHours(),
    )

    created = repo.add_store(new_store)
    assert created.id > 0
    assert created.name == "Apex Retail - Test Lab"
    assert created.amenities.drive_thru is True

    fetched = repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.city == "San Jose"


def test_search_nearby_radius(repo: StoreRepository):
    """Search around San Francisco center should find SF stores and exclude distant stores."""
    sf_lat, sf_lng = 37.7749, -122.4194

    # 15 km radius should include SF stores but exclude NYC/Seattle
    results = repo.search_nearby(sf_lat, sf_lng, radius_km=15.0)
    assert len(results) >= 4

    for item in results:
        assert item.distance_km <= 15.0
        assert item.store.city in ("San Francisco", "Oakland", "Berkeley")


def test_search_nearby_amenity_filter(repo: StoreRepository):
    """Search filtering by drive-thru amenity should return only drive-thru equipped stores."""
    sf_lat, sf_lng = 37.7749, -122.4194
    results = repo.search_nearby(sf_lat, sf_lng, radius_km=30.0, amenity="drive_thru")

    assert len(results) > 0
    for item in results:
        assert item.store.amenities.drive_thru is True


def test_search_nearby_min_rating(repo: StoreRepository):
    """Search filtering by minimum rating should return only highly rated stores."""
    sf_lat, sf_lng = 37.7749, -122.4194
    results = repo.search_nearby(sf_lat, sf_lng, radius_km=50.0, min_rating=4.8)

    assert len(results) > 0
    for item in results:
        assert item.store.rating >= 4.8
