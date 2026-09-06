# tests/test_polyline.py
# Unit tests for Google Maps encoded polyline encoding and decoding algorithms.
# Connects to: src/utils/polyline.py
# Created: 2026-09-06

import pytest
from src.utils.polyline import decode_polyline, encode_polyline


def test_polyline_empty_inputs():
    """Empty coordinate list should encode to empty string and vice versa."""
    assert encode_polyline([]) == ""
    assert decode_polyline("") == []


def test_polyline_round_trip():
    """Encoding and decoding coordinates should preserve coordinates within 5 decimal places (~1m)."""
    original_points = [
        (37.77493, -122.41942),
        (37.78583, -122.40642),
        (37.78783, -122.40613),
    ]

    encoded = encode_polyline(original_points)
    assert isinstance(encoded, str)
    assert len(encoded) > 0

    decoded = decode_polyline(encoded)
    assert len(decoded) == len(original_points)

    for (orig_lat, orig_lng), pt in zip(original_points, decoded):
        assert pt.latitude == pytest.approx(orig_lat, abs=1e-4)
        assert pt.longitude == pytest.approx(orig_lng, abs=1e-4)
