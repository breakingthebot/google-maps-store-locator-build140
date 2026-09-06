# src/models/store.py
# Retail store entities, operating hours, ratings, and amenity schemas.
# Connects to: src/models/geo.py, src/utils/hours.py, src/services/store_repository.py
# Created: 2026-09-06

from datetime import time
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from src.models.geo import Coordinates


class DayOfWeek(str, Enum):
    """Enumeration of days of the week."""

    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class DayHours(BaseModel):
    """Operating hours for a single day of the week."""

    open_time: Optional[str] = Field("08:00", description="Opening time in 24-hour HH:MM format e.g. '08:00'")
    close_time: Optional[str] = Field("21:00", description="Closing time in 24-hour HH:MM format e.g. '21:00'")
    is_closed: bool = Field(False, description="True if the store is closed all day")

    @field_validator("open_time", "close_time")
    @classmethod
    def validate_time_format(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v != "":
            parts = v.split(":")
            if len(parts) != 2:
                raise ValueError("Time must be in HH:MM format")
            h, m = int(parts[0]), int(parts[1])
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError("Hours must be 00-23 and minutes 00-59")
        return v


class WeeklyHours(BaseModel):
    """Weekly operating schedule for Monday through Sunday."""

    monday: DayHours = Field(default_factory=lambda: DayHours(open_time="08:00", close_time="21:00"))
    tuesday: DayHours = Field(default_factory=lambda: DayHours(open_time="08:00", close_time="21:00"))
    wednesday: DayHours = Field(default_factory=lambda: DayHours(open_time="08:00", close_time="21:00"))
    thursday: DayHours = Field(default_factory=lambda: DayHours(open_time="08:00", close_time="21:00"))
    friday: DayHours = Field(default_factory=lambda: DayHours(open_time="08:00", close_time="22:00"))
    saturday: DayHours = Field(default_factory=lambda: DayHours(open_time="09:00", close_time="22:00"))
    sunday: DayHours = Field(default_factory=lambda: DayHours(open_time="10:00", close_time="19:00"))

    def get_day(self, day_name: str) -> DayHours:
        """Fetch hours for a given day name (case-insensitive)."""
        clean_day = day_name.strip().lower()
        if hasattr(self, clean_day):
            return getattr(self, clean_day)
        return self.monday


# Alias for backward compatibility
StoreHours = WeeklyHours


class StoreReview(BaseModel):
    """Verified customer rating and testimonial."""

    author_name: str
    rating: float = Field(..., ge=1.0, le=5.0)
    text: str
    relative_time_description: str = "recently"
    created_at: Optional[str] = None


class StoreAmenities(BaseModel):
    """Store amenities and service features."""

    drive_thru: bool = False
    curbside_pickup: bool = True
    ev_charging: bool = False
    wheelchair_accessible: bool = True
    wifi: bool = True
    in_store_shopping: bool = True


class StoreBase(BaseModel):
    """Common attributes for store models."""

    name: str = Field(..., min_length=1, description="Store branch name e.g. 'Apex Retail - Downtown'")
    brand: str = Field("Apex Retail", description="Brand or franchise name")
    street: str = Field(..., min_length=1, description="Street address")
    city: str = Field(..., min_length=1, description="City name")
    state: str = Field(..., min_length=2, description="State / Province code or name")
    postal_code: str = Field(..., min_length=3, description="Postal / ZIP code")
    country: str = Field("US", description="Country code e.g. 'US'")
    phone: str = Field("", description="Contact telephone number")
    website: str = Field("", description="Store official website or landing page")
    email: str = Field("", description="Customer support email")
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    amenities: StoreAmenities = Field(default_factory=StoreAmenities)
    hours: WeeklyHours = Field(default_factory=WeeklyHours)


class StoreCreate(StoreBase):
    """Payload for creating a new store location."""

    pass


class Store(StoreBase):
    """Complete persistent store entity with rating aggregates and reviews."""

    id: int = Field(..., description="Unique integer primary key")
    rating: float = Field(default=4.5, ge=0.0, le=5.0, description="Average customer rating out of 5")
    user_ratings_total: int = Field(default=0, ge=0, description="Total count of customer reviews")
    place_id: Optional[str] = Field(None, description="Google Maps Place ID if linked")
    reviews: list[StoreReview] = Field(default_factory=list, description="Recent customer reviews")

    @property
    def coordinates(self) -> Coordinates:
        """Return store location as a Coordinates instance."""
        return Coordinates(latitude=self.latitude, longitude=self.longitude)

    @property
    def full_address(self) -> str:
        """Return the combined single-line formatted street address."""
        return f"{self.street}, {self.city}, {self.state} {self.postal_code}, {self.country}"


class StoreSummary(BaseModel):
    """Enriched store search result with calculated distance and live operational status."""

    store: Store
    distance_km: float = Field(..., ge=0.0, description="Calculated Haversine distance in kilometers")
    distance_miles: float = Field(..., ge=0.0, description="Calculated distance in miles")
    is_open_now: bool = Field(..., description="True if store is open right now based on operating hours")
    status_text: str = Field(..., description="Status string e.g. 'Open until 9:00 PM' or 'Closed'")
    closing_soon: bool = Field(False, description="True if store closes within 45 minutes")
