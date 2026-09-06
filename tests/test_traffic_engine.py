# tests/test_traffic_engine.py
# Unit tests for real-time traffic calculation engine, diurnal curves, and predictive matrix
# Connects to: src/services/traffic_engine.py, src/models/traffic.py
# Created: 2026-09-06

import pytest
from datetime import datetime
from src.models.directions import TravelMode
from src.models.geo import Coordinates
from src.models.traffic import TrafficModel, TrafficCondition
from src.services.traffic_engine import (
    parse_departure_time,
    calculate_congestion_factor,
    segment_route_traffic,
    predict_departure_matrix,
    get_arterial_traffic_overlay,
)


def test_parse_departure_time_presets():
    """Test standard named presets for departure times."""
    dec_now, label_now, dt_now = parse_departure_time("now")
    assert isinstance(dt_now, datetime)
    assert "Now" in label_now

    dec_morn, label_morn, dt_morn = parse_departure_time("morning_rush")
    assert dec_morn == 8.5
    assert dt_morn.hour == 8 and dt_morn.minute == 30

    dec_mid, label_mid, dt_mid = parse_departure_time("midday")
    assert dec_mid == 12.5
    assert dt_mid.hour == 12 and dt_mid.minute == 30

    dec_eve, label_eve, dt_eve = parse_departure_time("evening_rush")
    assert dec_eve == 17.5
    assert dt_eve.hour == 17 and dt_eve.minute == 30

    dec_off, label_off, dt_off = parse_departure_time("off_peak")
    assert dec_off == 21.5
    assert dt_off.hour == 21 and dt_off.minute == 30


def test_parse_departure_time_formats():
    """Test 24h, 12h, and ISO time string parsing."""
    dec1, _, dt1 = parse_departure_time("14:45")
    assert round(dec1, 2) == 14.75
    assert dt1.hour == 14 and dt1.minute == 45

    dec2, _, dt2 = parse_departure_time("09:15 AM")
    assert round(dec2, 2) == 9.25
    assert dt2.hour == 9 and dt2.minute == 15

    dec3, _, dt3 = parse_departure_time("5:30 PM")
    assert round(dec3, 2) == 17.5
    assert dt3.hour == 17 and dt3.minute == 30

    dec4, _, dt4 = parse_departure_time("2026-09-06T18:00:00")
    assert dec4 == 18.0
    assert dt4.hour == 18 and dt4.minute == 0


def test_calculate_congestion_factor_diurnal_curve():
    """Test congestion multipliers during morning peak, evening peak, and off-peak night."""
    # Morning rush peak at 08:30 (8.5)
    factor_morn, cond_morn = calculate_congestion_factor(
        8.5,
        mode=TravelMode.DRIVING,
        traffic_model=TrafficModel.BEST_GUESS,
    )
    assert factor_morn > 1.3
    assert cond_morn in (TrafficCondition.MODERATE, TrafficCondition.HEAVY)

    # Evening peak at 17:30 (17.5)
    factor_eve, cond_eve = calculate_congestion_factor(
        17.5,
        mode=TravelMode.DRIVING,
        traffic_model=TrafficModel.BEST_GUESS,
    )
    assert factor_eve >= 1.5
    assert cond_eve in (TrafficCondition.HEAVY, TrafficCondition.SEVERE)

    # Off-peak night at 02:00 (2.0)
    factor_night, cond_night = calculate_congestion_factor(
        2.0,
        mode=TravelMode.DRIVING,
        traffic_model=TrafficModel.BEST_GUESS,
    )
    assert factor_night == 1.0
    assert cond_night == TrafficCondition.CLEAR


def test_calculate_congestion_factor_models():
    """Test optimistic and pessimistic traffic model adjustments."""
    best_guess, _ = calculate_congestion_factor(17.5, mode=TravelMode.DRIVING, traffic_model=TrafficModel.BEST_GUESS)
    optimistic, _ = calculate_congestion_factor(17.5, mode=TravelMode.DRIVING, traffic_model=TrafficModel.OPTIMISTIC)
    pessimistic, _ = calculate_congestion_factor(17.5, mode=TravelMode.DRIVING, traffic_model=TrafficModel.PESSIMISTIC)

    assert optimistic < best_guess
    assert pessimistic > best_guess


def test_calculate_congestion_factor_non_driving():
    """Walking, transit, and bicycling should not suffer road traffic congestion."""
    for non_drive_mode in (TravelMode.WALKING, TravelMode.BICYCLING, TravelMode.TRANSIT):
        factor, cond = calculate_congestion_factor(17.5, mode=non_drive_mode)
        assert factor == 1.0
        assert cond == TrafficCondition.CLEAR


def test_segment_route_traffic():
    """Test splitting a route coordinate array into colored traffic segments."""
    coords = [
        Coordinates(latitude=37.77, longitude=-122.41),
        Coordinates(latitude=37.78, longitude=-122.42),
        Coordinates(latitude=37.79, longitude=-122.43),
        Coordinates(latitude=37.80, longitude=-122.44),
    ]

    segments = segment_route_traffic(
        route_coords=coords,
        total_distance_meters=5000,
        base_duration_seconds=1200,
        overall_factor=1.55,
        overall_condition=TrafficCondition.HEAVY,
    )

    assert len(segments) >= 2
    assert all(hasattr(s, "color_hex") for s in segments)
    assert all(s.polyline for s in segments)
    assert sum(s.duration_seconds for s in segments) > 0


def test_predict_departure_matrix():
    """Test matrix generation across the 5 canonical departure windows."""
    matrix = predict_departure_matrix(
        base_duration_seconds=1800,
        travel_distance_km=15.0,
        traffic_model=TrafficModel.BEST_GUESS,
        mode=TravelMode.DRIVING,
    )

    assert len(matrix.predictions) == 5
    assert matrix.best_window is not None
    assert matrix.worst_window is not None
    assert matrix.max_time_saved_seconds >= 0
    # Best window should have less or equal duration to worst window
    assert matrix.best_window.duration_in_traffic_seconds <= matrix.worst_window.duration_in_traffic_seconds


def test_get_arterial_traffic_overlay():
    """Test arterial overlay dataset generation."""
    arterials = get_arterial_traffic_overlay()
    assert len(arterials) >= 6
    assert any("Market St" in a["name"] or "101" in a["name"] or "Broadway" in a["name"] for a in arterials)
    assert all(a["color_hex"].startswith("#") for a in arterials)
