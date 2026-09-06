# src/models/directions.py
# Navigation directions, routing steps, and polyline models.
# Connects to: src/models/geo.py, src/services/google_maps.py, src/utils/polyline.py
# Created: 2026-09-06

from enum import Enum
from typing import Optional, Union
from pydantic import BaseModel, Field
from src.models.geo import Coordinates


class TravelMode(str, Enum):
    """Supported transportation travel modes for route calculation."""

    DRIVING = "driving"
    WALKING = "walking"
    BICYCLING = "bicycling"
    TRANSIT = "transit"


class RouteStep(BaseModel):
    """A discrete turn or instruction in a calculated navigation route."""

    instruction: str = Field(..., description="Turn-by-turn instruction e.g. 'Turn right onto Market St'")
    distance_meters: int = Field(..., ge=0, description="Step distance in meters")
    distance_text: str = Field(..., description="Human-readable distance e.g. '0.4 mi'")
    duration_seconds: int = Field(..., ge=0, description="Step duration in seconds")
    duration_text: str = Field(..., description="Human-readable duration e.g. '2 mins'")
    start_location: Coordinates
    end_location: Coordinates
    travel_mode: TravelMode = TravelMode.DRIVING


class DirectionsRequest(BaseModel):
    """Input parameters requesting a route between two locations."""

    origin: Union[str, Coordinates] = Field(..., description="Address string or coordinates of origin")
    destination: Union[str, Coordinates] = Field(..., description="Address string or coordinates of destination")
    mode: TravelMode = Field(default=TravelMode.DRIVING, description="Travel mode (driving, walking, bicycling, transit)")
    avoid_tolls: bool = False
    avoid_highways: bool = False


class DirectionsResult(BaseModel):
    """Calculated route between origin and destination with full turn-by-turn steps."""

    origin_address: str
    destination_address: str
    mode: TravelMode
    total_distance_km: float = Field(..., ge=0.0)
    total_distance_miles: float = Field(..., ge=0.0)
    distance_text: str
    total_duration_seconds: int = Field(..., ge=0)
    duration_text: str
    overview_polyline: str = Field(..., description="Google Maps encoded polyline string")
    route_coordinates: list[Coordinates] = Field(default_factory=list, description="Decoded lat/lng points along the path")
    steps: list[RouteStep] = Field(default_factory=list, description="Ordered turn-by-turn routing steps")
