# src/models/trip.py
# Pydantic data schemas for multi-stop trip planning, waypoint ordering, and route optimization.
# Connects to: src/models/geo.py, src/models/directions.py, src/models/store.py
# Created: 2026-09-06

from typing import List, Optional
from pydantic import BaseModel, Field
from src.models.directions import RouteStep, TravelMode
from src.models.geo import Coordinates
from src.models.store import StoreSummary


class WaypointNode(BaseModel):
    """A node in a multi-stop itinerary."""

    sequence_index: int = Field(..., description="0-indexed order of visit")
    name: str = Field(..., description="Display name for this stop")
    address: str = Field(..., description="Street or formatted address")
    coordinates: Coordinates = Field(..., description="Latitude and Longitude")
    store_id: Optional[int] = Field(None, description="Store ID if this node represents a store")
    is_origin: bool = Field(False, description="True if this is the trip start point")
    is_destination: bool = Field(False, description="True if this is the trip end point")


class TripLeg(BaseModel):
    """A single leg of travel between two consecutive stops."""

    leg_index: int = Field(..., description="0-indexed sequence of this leg")
    start_node: WaypointNode = Field(..., description="Departure stop")
    end_node: WaypointNode = Field(..., description="Arrival stop")
    distance_km: float = Field(..., description="Leg distance in kilometers")
    distance_miles: float = Field(..., description="Leg distance in miles")
    distance_text: str = Field(..., description="Formatted distance string, e.g. '4.2 mi'")
    duration_minutes: float = Field(..., description="Leg duration in minutes")
    duration_text: str = Field(..., description="Formatted duration string, e.g. '12 mins'")
    steps: List[RouteStep] = Field(default_factory=list, description="Turn-by-turn navigation steps")
    polyline: str = Field("", description="Google-encoded polyline string for this leg")


class TripSavings(BaseModel):
    """Quantified distance and travel time savings gained from TSP route optimization."""

    naive_distance_km: float = Field(..., description="Total distance if visited in raw input order")
    optimized_distance_km: float = Field(..., description="Optimized total distance")
    distance_saved_km: float = Field(..., description="Kilometers saved")
    distance_saved_miles: float = Field(..., description="Miles saved")
    percentage_distance_saved: float = Field(..., description="Percent reduction in travel distance")
    estimated_minutes_saved: float = Field(..., description="Estimated drive/travel time saved in minutes")


class TripPlanRequest(BaseModel):
    """Request payload to plan an optimized multi-stop trip."""

    origin: str = Field(..., description="Starting location name, address, or 'lat,lng' string")
    origin_coordinates: Optional[Coordinates] = Field(None, description="Explicit origin coordinates if already known")
    store_ids: List[int] = Field(..., min_length=2, max_length=12, description="Store IDs to visit (2 to 12 stores)")
    round_trip: bool = Field(True, description="Whether to return to origin after visiting all stores")
    optimize: bool = Field(True, description="Whether to apply TSP optimization to minimize total distance")
    travel_mode: TravelMode = Field(TravelMode.DRIVING, description="Travel mode (driving, walking, bicycling, transit)")


class TripPlanResponse(BaseModel):
    """Calculated itinerary response with optimized visit order, legs, and cumulative metrics."""

    origin_label: str = Field(..., description="Origin display label")
    destination_label: str = Field(..., description="Final destination display label")
    round_trip: bool = Field(..., description="Whether trip returns to start")
    travel_mode: TravelMode = Field(..., description="Travel mode utilized")
    optimized: bool = Field(..., description="Whether route was re-ordered by TSP optimizer")
    optimized_store_ids: List[int] = Field(..., description="List of store IDs in the calculated visit order")
    stops: List[WaypointNode] = Field(..., description="All stops in chronological order")
    legs: List[TripLeg] = Field(..., description="Navigation legs between stops")
    total_distance_km: float = Field(..., description="Cumulative distance in kilometers")
    total_distance_miles: float = Field(..., description="Cumulative distance in miles")
    total_distance_text: str = Field(..., description="Formatted total distance string")
    total_duration_minutes: float = Field(..., description="Cumulative travel duration in minutes")
    total_duration_text: str = Field(..., description="Formatted total duration string")
    overview_polyline: str = Field(..., description="Composite Google-encoded polyline covering the entire trip")
    savings: Optional[TripSavings] = Field(None, description="Savings metrics if route was optimized")
