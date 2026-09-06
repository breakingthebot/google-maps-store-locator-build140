# src/models/geo.py
# Geographic domain models including coordinates, bounding boxes, and geocoding results.
# Connects to: src/utils/distance.py, src/services/google_maps.py
# Created: 2026-09-06

from typing import Optional
from pydantic import BaseModel, Field, field_validator


class Coordinates(BaseModel):
    """Geographic point representing latitude and longitude in decimal degrees."""

    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude between -90 and 90")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude between -180 and 180")

    @property
    def lat(self) -> float:
        """Alias for latitude."""
        return self.latitude

    @property
    def lng(self) -> float:
        """Alias for longitude."""
        return self.longitude

    def to_tuple(self) -> tuple[float, float]:
        """Return coordinates as (latitude, longitude) tuple."""
        return (self.latitude, self.longitude)


class BoundingBox(BaseModel):
    """Geographic rectangle defined by minimum and maximum latitude and longitude."""

    min_latitude: float = Field(..., ge=-90.0, le=90.0)
    max_latitude: float = Field(..., ge=-90.0, le=90.0)
    min_longitude: float = Field(..., ge=-180.0, le=180.0)
    max_longitude: float = Field(..., ge=-180.0, le=180.0)

    def contains(self, point: Coordinates) -> bool:
        """Check if a coordinate point falls inside this bounding box."""
        lat_match = self.min_latitude <= point.latitude <= self.max_latitude
        if self.min_longitude <= self.max_longitude:
            lng_match = self.min_longitude <= point.longitude <= self.max_longitude
        else:
            # Crosses the antimeridian
            lng_match = point.longitude >= self.min_longitude or point.longitude <= self.max_longitude
        return lat_match and lng_match


class DistanceResult(BaseModel):
    """Calculated distance and duration metrics between two points."""

    distance_km: float = Field(..., ge=0.0, description="Distance in kilometers")
    distance_miles: float = Field(..., ge=0.0, description="Distance in statute miles")
    duration_seconds: Optional[int] = Field(None, ge=0, description="Estimated transit duration in seconds")
    duration_text: Optional[str] = Field(None, description="Human-readable duration e.g. '18 mins'")


class GeocodeResult(BaseModel):
    """Normalized geocoding outcome from address resolution or reverse geocoding."""

    formatted_address: str
    coordinates: Coordinates
    place_id: Optional[str] = None
    street_number: Optional[str] = None
    route: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = "US"
