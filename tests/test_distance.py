# tests/test_distance.py
# Unit tests for Haversine great-circle distance, bounding box calculations, and compass bearings.
# Connects to: src/utils/distance.py, src/models/geo.py
# Created: 2026-09-06

import pytest
from src.models.geo import Coordinates
from src.utils.distance import (
    calculate_bearing,
    calculate_bounding_box,
    haversine_distance_km,
    haversine_distance_miles,
)


def test_haversine_identical_points():
    """Distance between identical coordinates should be exactly 0."""
    dist = haversine_distance_km(37.7749, -122.4194, 37.7749, -122.4194)
    assert dist == 0.0
    assert haversine_distance_miles(37.7749, -122.4194, 37.7749, -122.4194) == 0.0


def test_haversine_known_distances():
    """Verify known geographic distances between San Francisco and Oakland (~13.5 km)."""
    sf_lat, sf_lng = 37.7749, -122.4194
    oak_lat, oak_lng = 37.8044, -122.2712

    km = haversine_distance_km(sf_lat, sf_lng, oak_lat, oak_lng)
    miles = haversine_distance_miles(sf_lat, sf_lng, oak_lat, oak_lng)

    assert 12.0 < km < 15.0
    assert 7.5 < miles < 9.5
    assert round(km * 0.621371, 2) == pytest.approx(miles, abs=0.1)


def test_haversine_cross_country():
    """Verify long-range distance calculation between San Francisco and New York (~4130 km)."""
    sf_lat, sf_lng = 37.7749, -122.4194
    ny_lat, ny_lng = 40.7128, -74.0060

    km = haversine_distance_km(sf_lat, sf_lng, ny_lat, ny_lng)
    assert 4100.0 < km < 4200.0


def test_calculate_bounding_box():
    """Bounding box calculation should enclose the origin and span the search radius."""
    center_lat, center_lng = 37.7749, -122.4194
    radius_km = 25.0

    bbox = calculate_bounding_box(center_lat, center_lng, radius_km)

    # Origin must be strictly inside the bounding box
    origin = Coordinates(latitude=center_lat, longitude=center_lng)
    assert bbox.contains(origin)

    assert bbox.min_latitude < center_lat < bbox.max_latitude
    assert bbox.min_longitude < center_lng < bbox.max_longitude

    # Latitude span should match delta ~ radius / 111
    lat_span = bbox.max_latitude - bbox.min_latitude
    assert 0.40 < lat_span < 0.50


def test_calculate_bearing():
    """Bearing calculations should accurately produce cardinal compass angles."""
    origin_lat, origin_lng = 37.7749, -122.4194

    # Point directly North
    north_bearing = calculate_bearing(origin_lat, origin_lng, origin_lat + 1.0, origin_lng)
    assert 355.0 <= north_bearing <= 360.0 or 0.0 <= north_bearing <= 5.0

    # Point East
    east_bearing = calculate_bearing(origin_lat, origin_lng, origin_lat, origin_lng + 1.0)
    assert 80.0 <= east_bearing <= 100.0

    # Point South
    south_bearing = calculate_bearing(origin_lat, origin_lng, origin_lat - 1.0, origin_lng)
    assert 170.0 <= south_bearing <= 190.0
