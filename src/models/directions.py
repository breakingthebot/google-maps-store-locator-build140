# src/models/directions.py
# Navigation directions, routing steps, and polyline models.
# Connects to: src/models/geo.py, src/services/google_maps.py, src/utils/polyline.py
# Created: 2026-09-06

from enum import Enum
from typing import List, Optional, Union
from pydantic import BaseModel, Field
from src.models.geo import Coordinates
from src.models.traffic import TrafficCondition, TrafficModel, TrafficSegment


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
    duration_in_traffic_seconds: Optional[int] = Field(None, description="Duration in traffic in seconds if modeled")
    duration_in_traffic_text: Optional[str] = Field(None, description="Formatted duration in traffic")
    traffic_condition: TrafficCondition = Field(TrafficCondition.CLEAR, description="Congestion condition for this step")


class DirectionsRequest(BaseModel):
    """Input parameters requesting a route between two locations."""

    origin: Union[str, Coordinates] = Field(..., description="Address string or coordinates of origin")
    destination: Union[str, Coordinates] = Field(..., description="Address string or coordinates of destination")
    mode: TravelMode = Field(default=TravelMode.DRIVING, description="Travel mode (driving, walking, bicycling, transit)")
    avoid_tolls: bool = False
    avoid_highways: bool = False
    departure_time: Optional[Union[str, int]] = Field(None, description="'now', epoch timestamp, or time string e.g. '08:30'")
    traffic_model: TrafficModel = Field(default=TrafficModel.BEST_GUESS, description="Traffic model heuristic")


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
    duration_in_traffic_seconds: Optional[int] = Field(None, ge=0, description="Duration under traffic conditions")
    duration_in_traffic_text: Optional[str] = Field(None, description="Formatted duration with traffic")
    traffic_condition: TrafficCondition = Field(default=TrafficCondition.CLEAR, description="Overall traffic condition")
    traffic_delay_seconds: int = Field(default=0, ge=0, description="Delay above free-flow travel time")
    traffic_delay_text: str = Field(default="0 min", description="Formatted traffic delay")
    overview_polyline: str = Field(..., description="Google Maps encoded polyline string")
    route_coordinates: list[Coordinates] = Field(default_factory=list, description="Decoded lat/lng points along the path")
    steps: list[RouteStep] = Field(default_factory=list, description="Ordered turn-by-turn routing steps")
    traffic_segments: List[TrafficSegment] = Field(default_factory=list, description="Color-coded route sections by congestion")

