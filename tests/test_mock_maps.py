# tests/test_mock_maps.py
# Unit tests for the high-fidelity offline Google Maps simulation engine.
# Connects to: src/services/mock_maps.py, src/models/directions.py, src/models/geo.py
# Created: 2026-09-06

import pytest
from src.models.directions import TravelMode
from src.models.geo import Coordinates
from src.services.mock_maps import MockGoogleMapsService


def test_mock_geocoding_known_cities():
    """Mock geocoding should return accurate coordinates for major metropolitan centers."""
    service = MockGoogleMapsService()

    sf = service.geocode("San Francisco")
    assert sf is not None
    assert sf.coordinates.latitude == pytest.approx(37.7749, abs=0.01)
    assert sf.coordinates.longitude == pytest.approx(-122.4194, abs=0.01)
    assert "San Francisco" in sf.formatted_address

    ny = service.geocode("Times Square, New York")
    assert ny is not None
    assert ny.coordinates.latitude == pytest.approx(40.7588, abs=0.01)
    assert ny.coordinates.longitude == pytest.approx(-73.9851, abs=0.01)


def test_mock_geocoding_postal_code():
    """Mock geocoding should resolve valid postal codes."""
    service = MockGoogleMapsService()
    res = service.geocode("94102")
    assert res is not None
    assert res.postal_code == "94102"
    assert res.state == "CA"


def test_mock_geocoding_fallback():
    """Unknown queries should generate deterministic, valid coordinates."""
    service = MockGoogleMapsService()
    res1 = service.geocode("Unknown Test Lane 123")
    res2 = service.geocode("Unknown Test Lane 123")
    assert res1 is not None
    assert res2 is not None
    assert res1.coordinates.latitude == res2.coordinates.latitude
    assert res1.coordinates.longitude == res2.coordinates.longitude


def test_mock_reverse_geocoding():
    """Reverse geocoding coordinates near known locations should yield reference addresses."""
    service = MockGoogleMapsService()
    res = service.reverse_geocode(37.7878, -122.4061)
    assert res is not None
    assert "San Francisco" in res.formatted_address


def test_mock_directions_routing():
    """Directions engine should calculate realistic distance, duration, steps, and polyline."""
    service = MockGoogleMapsService()
    origin = Coordinates(latitude=37.7749, longitude=-122.4194)
    destination = Coordinates(latitude=37.7878, longitude=-122.4061)

    result = service.directions(origin, destination, mode=TravelMode.DRIVING)

    assert result.total_distance_km > 0
    assert result.total_duration_seconds > 0
    assert len(result.steps) >= 3
    assert len(result.overview_polyline) > 0
    assert len(result.route_coordinates) >= 3
    assert result.mode == TravelMode.DRIVING
