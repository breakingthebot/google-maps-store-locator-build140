# src/models/traffic.py
# Pydantic schemas for real-time traffic conditions, congestion models, and predictive departure analysis.
# Connects to: src/models/geo.py, src/models/directions.py
# Created: 2026-09-06

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from src.models.geo import Coordinates


class TrafficModel(str, Enum):
    """Google Maps Traffic Model heuristics."""

    BEST_GUESS = "best_guess"
    OPTIMISTIC = "optimistic"
    PESSIMISTIC = "pessimistic"


class TrafficCondition(str, Enum):
    """Traffic congestion severity levels."""

    CLEAR = "clear"         # Free-flow traffic (speed factor <= 1.15)
    MODERATE = "moderate"   # Medium density / slight slowdown (1.15 < factor <= 1.40)
    HEAVY = "heavy"         # Significant congestion / stop-and-go (1.40 < factor <= 1.70)
    SEVERE = "severe"       # Gridlock / severe delay (factor > 1.70)


class TrafficSegment(BaseModel):
    """A discrete route section with its specific traffic flow condition and color code."""

    segment_index: int = Field(..., description="0-indexed sequence of this traffic segment")
    start_location: Coordinates = Field(..., description="Beginning point of segment")
    end_location: Coordinates = Field(..., description="Ending point of segment")
    condition: TrafficCondition = Field(..., description="Congestion severity level")
    speed_factor: float = Field(..., ge=0.5, description="Travel delay factor (1.0 = baseline normal)")
    polyline: str = Field("", description="Google-encoded polyline string for this segment")
    color_hex: str = Field("#10b981", description="Color code e.g. #10b981 (clear), #f59e0b (moderate), #ef4444 (heavy)")
    distance_meters: int = Field(..., ge=0, description="Length of segment in meters")
    duration_seconds: int = Field(..., ge=0, description="Travel duration under traffic conditions")


class DepartureWindowPrediction(BaseModel):
    """Predicted travel time metrics for a specific departure time window."""

    departure_label: str = Field(..., description="Human-readable departure time, e.g. '8:30 AM (Morning Rush)'")
    departure_time_iso: str = Field(..., description="ISO datetime string")
    departure_hour: float = Field(..., description="Decimal hour of day (0.0 - 24.0)")
    condition: TrafficCondition = Field(..., description="Expected traffic condition")
    duration_in_traffic_seconds: int = Field(..., ge=0, description="Estimated duration under traffic")
    duration_in_traffic_text: str = Field(..., description="Formatted duration string, e.g. '34 mins'")
    delay_minutes: float = Field(..., ge=0.0, description="Estimated delay above free-flow travel time")
    is_recommended: bool = Field(False, description="True if this departure window minimizes congestion")
    time_saved_vs_worst_minutes: float = Field(0.0, description="Minutes saved compared to worst rush-hour window")
    traffic_model: TrafficModel = Field(TrafficModel.BEST_GUESS, description="Traffic model heuristic applied")
    window_key: str = Field("", description="Preset key e.g. 'morning_rush'")
    label: str = Field("", description="Display label alias")
    time_range: str = Field("", description="Time of day interval string")
    traffic_condition: str = Field("", description="Traffic condition text")


class PredictiveDepartureResponse(BaseModel):
    """Comparative analysis of departure times across the day to find the optimal travel window."""

    origin_label: str = Field(..., description="Starting location name or address")
    destination_label: str = Field(..., description="Destination location name or address")
    base_duration_seconds: int = Field(..., ge=0, description="Free-flow duration without traffic")
    base_duration_text: str = Field(..., description="Formatted free-flow duration")
    travel_distance_km: float = Field(..., ge=0.0, description="Trip distance in kilometers")
    travel_distance_miles: float = Field(..., ge=0.0, description="Trip distance in miles")
    traffic_model: TrafficModel = Field(..., description="Traffic model applied")
    best_departure_time: str = Field(..., description="Recommended departure window with minimal delay")
    worst_departure_time: str = Field(..., description="Peak congestion window with maximum delay")
    max_time_saved_minutes: float = Field(..., ge=0.0, description="Maximum minutes saved by traveling off-peak")
    windows: List[DepartureWindowPrediction] = Field(..., description="Chronological departure windows throughout the day")
    predictions: List[DepartureWindowPrediction] = Field(default_factory=list, description="Alias for windows")
    best_window: Optional[DepartureWindowPrediction] = Field(None, description="Recommended departure window")
    worst_window: Optional[DepartureWindowPrediction] = Field(None, description="Worst departure window")
    max_time_saved_seconds: int = Field(0, description="Maximum time saved in seconds")

