# src/utils/distance.py
# High-precision geospatial calculations: Haversine distance, bounding box, and compass bearings.
# Connects to: src/models/geo.py, src/services/store_repository.py
# Created: 2026-09-06

import math
from src.models.geo import BoundingBox, Coordinates

EARTH_RADIUS_KM: float = 6371.0088
KM_TO_MILES: float = 0.621371192


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two coordinate pairs in kilometers using Haversine formula.

    Args:
        lat1: Latitude of point 1 in degrees.
        lon1: Longitude of point 1 in degrees.
        lat2: Latitude of point 2 in degrees.
        lon2: Longitude of point 2 in degrees.

    Returns:
        Distance in kilometers rounded to 2 decimal places.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    # Clip to 1.0 to handle floating point errors for identical/antipodal coordinates
    a = min(1.0, max(0.0, a))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    distance = EARTH_RADIUS_KM * c
    return round(distance, 2)


def haversine_distance_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points in statute miles.

    Args:
        lat1: Latitude of point 1 in degrees.
        lon1: Longitude of point 1 in degrees.
        lat2: Latitude of point 2 in degrees.
        lon2: Longitude of point 2 in degrees.

    Returns:
        Distance in miles rounded to 2 decimal places.
    """
    km = haversine_distance_km(lat1, lon1, lat2, lon2)
    return round(km * KM_TO_MILES, 2)


def calculate_bounding_box(lat: float, lon: float, radius_km: float) -> BoundingBox:
    """Compute a latitude/longitude bounding rectangle enclosing a circular search radius.

    Enables indexed pre-filtering in SQL before calculating exact Haversine distances.

    Args:
        lat: Center point latitude in degrees.
        lon: Center point longitude in degrees.
        radius_km: Search radius in kilometers.

    Returns:
        BoundingBox with min/max latitude and longitude.
    """
    lat_rad = math.radians(lat)
    # 1 degree of latitude is approximately 111.0 km
    delta_lat = radius_km / 111.0
    min_lat = max(-90.0, lat - delta_lat)
    max_lat = min(90.0, lat + delta_lat)

    # 1 degree of longitude scales with cos(latitude)
    cos_lat = math.cos(lat_rad)
    if abs(cos_lat) > 1e-6:
        delta_lon = radius_km / (111.0 * cos_lat)
        min_lon = lon - delta_lon
        max_lon = lon + delta_lon
    else:
        # Near poles, encompass all longitudes
        min_lon = -180.0
        max_lon = 180.0

    # Normalize longitude to [-180, 180]
    if min_lon < -180.0:
        min_lon += 360.0
    if max_lon > 180.0:
        max_lon -= 360.0

    return BoundingBox(
        min_latitude=round(min_lat, 6),
        max_latitude=round(max_lat, 6),
        min_longitude=round(min_lon, 6),
        max_longitude=round(max_lon, 6),
    )


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the initial compass bearing from point 1 to point 2 in degrees (0 - 360).

    Args:
        lat1: Origin latitude in degrees.
        lon1: Origin longitude in degrees.
        lat2: Target latitude in degrees.
        lon2: Target longitude in degrees.

    Returns:
        Bearing in degrees from true North (0 = North, 90 = East, 180 = South, 270 = West).
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lambda = math.radians(lon2 - lon1)

    y = math.sin(delta_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
    bearing_rad = math.atan2(y, x)
    bearing_deg = (math.degrees(bearing_rad) + 360.0) % 360.0
    return round(bearing_deg, 1)
