# src/utils/polyline.py
# Google Maps Encoded Polyline algorithm encoder and decoder.
# Connects to: src/models/directions.py, src/services/google_maps.py
# Created: 2026-09-06

from src.models.geo import Coordinates


def encode_coordinate(coordinate: float) -> str:
    """Encode a single coordinate component using Google's polyline algorithm."""
    coord = round(coordinate * 1e5)
    coord <<= 1
    if coord < 0:
        coord = ~coord

    encoded = []
    while coord >= 0x20:
        encoded.append(chr((0x20 | (coord & 0x1F)) + 63))
        coord >>= 5
    encoded.append(chr(coord + 63))
    return "".join(encoded)


def encode_polyline(points: list[tuple[float, float]]) -> str:
    """Encode a sequence of (latitude, longitude) pairs into an encoded polyline string.

    Args:
        points: List of (lat, lng) tuples in decimal degrees.

    Returns:
        Encoded polyline string.
    """
    if not points:
        return ""

    encoded_chunks = []
    prev_lat = 0
    prev_lng = 0

    for lat, lng in points:
        lat_int = round(lat * 1e5)
        lng_int = round(lng * 1e5)

        delta_lat = lat_int - prev_lat
        delta_lng = lng_int - prev_lng

        prev_lat = lat_int
        prev_lng = lng_int

        encoded_chunks.append(encode_coordinate(delta_lat / 1e5))
        encoded_chunks.append(encode_coordinate(delta_lng / 1e5))

    return "".join(encoded_chunks)


def decode_polyline(polyline_str: str) -> list[Coordinates]:
    """Decode a Google Maps encoded polyline string into a list of Coordinates.

    Args:
        polyline_str: Encoded polyline string.

    Returns:
        List of Coordinates along the polyline path.
    """
    if not polyline_str:
        return []

    coordinates: list[Coordinates] = []
    index = 0
    length = len(polyline_str)
    lat = 0
    lng = 0

    while index < length:
        # Decode latitude delta
        shift = 0
        result = 0
        while True:
            if index >= length:
                break
            byte = ord(polyline_str[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        delta_lat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += delta_lat

        # Decode longitude delta
        shift = 0
        result = 0
        while True:
            if index >= length:
                break
            byte = ord(polyline_str[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        delta_lng = ~(result >> 1) if (result & 1) else (result >> 1)
        lng += delta_lng

        coordinates.append(
            Coordinates(
                latitude=round(lat / 1e5, 6),
                longitude=round(lng / 1e5, 6),
            )
        )

    return coordinates
