# src/services/mock_maps.py
# High-fidelity offline simulation of Google Maps Platform Geocoding and Directions APIs.
# Connects to: src/models/geo.py, src/models/directions.py, src/utils/distance.py, src/utils/polyline.py
# Created: 2026-09-06

import hashlib
import math
from typing import Optional
from src.models.directions import DirectionsResult, RouteStep, TravelMode
from src.models.geo import Coordinates, GeocodeResult
from src.utils.distance import (
    calculate_bearing,
    haversine_distance_km,
    haversine_distance_miles,
)
from src.utils.polyline import encode_polyline

# Pre-seeded reference geocoding coordinates for deterministic offline testing
KNOWN_LOCATIONS: dict[str, tuple[float, float, str, str, str, str]] = {
    # key: (lat, lng, formatted_address, city, state, postal_code)
    "san francisco": (37.774929, -122.419416, "San Francisco, CA, USA", "San Francisco", "CA", "94102"),
    "market st": (37.785834, -122.406417, "760 Market St, San Francisco, CA 94102, USA", "San Francisco", "CA", "94102"),
    "mission": (37.759865, -122.414798, "Mission St, San Francisco, CA 94110, USA", "San Francisco", "CA", "94110"),
    "fisherman": (37.808000, -122.417743, "Fisherman's Wharf, San Francisco, CA 94133, USA", "San Francisco", "CA", "94133"),
    "soma": (37.778519, -122.405640, "SoMa, San Francisco, CA 94103, USA", "San Francisco", "CA", "94103"),
    "94102": (37.778687, -122.421242, "San Francisco, CA 94102, USA", "San Francisco", "CA", "94102"),
    "94103": (37.772640, -122.409860, "San Francisco, CA 94103, USA", "San Francisco", "CA", "94103"),
    "94110": (37.750000, -122.415000, "San Francisco, CA 94110, USA", "San Francisco", "CA", "94110"),
    "new york": (40.712776, -74.005974, "New York, NY, USA", "New York", "NY", "10007"),
    "manhattan": (40.783060, -73.971249, "Manhattan, New York, NY, USA", "New York", "NY", "10024"),
    "times square": (40.758896, -73.985130, "Times Square, Manhattan, NY 10036, USA", "New York", "NY", "10036"),
    "soho": (40.723301, -74.002988, "SoHo, New York, NY 10012, USA", "New York", "NY", "10012"),
    "10001": (40.750630, -73.997180, "New York, NY 10001, USA", "New York", "NY", "10001"),
    "seattle": (47.606209, -122.332071, "Seattle, WA, USA", "Seattle", "WA", "98104"),
    "pike place": (47.609657, -122.342148, "Pike Place Market, Seattle, WA 98101, USA", "Seattle", "WA", "98101"),
    "chicago": (41.878114, -87.629798, "Chicago, IL, USA", "Chicago", "IL", "60604"),
    "austin": (30.267153, -97.743061, "Austin, TX, USA", "Austin", "TX", "78701"),
    "los angeles": (34.052234, -118.243685, "Los Angeles, CA, USA", "Los Angeles", "CA", "90012"),
    "boston": (42.360082, -71.058880, "Boston, MA, USA", "Boston", "MA", "02108"),
    "denver": (39.739236, -104.990251, "Denver, CO, USA", "Denver", "CO", "80202"),
}

# Average city transit speeds in km/h by mode
SPEED_KMH: dict[TravelMode, float] = {
    TravelMode.DRIVING: 38.0,
    TravelMode.WALKING: 4.8,
    TravelMode.BICYCLING: 16.0,
    TravelMode.TRANSIT: 24.0,
}


class MockGoogleMapsService:
    """Simulates Google Maps Platform APIs for geocoding, reverse geocoding, and directions."""

    def __init__(self) -> None:
        self.provider_name = "Offline Mock Maps Engine"

    def geocode(self, query: str) -> Optional[GeocodeResult]:
        """Geocode an address, landmark, or zip code to coordinates.

        Matches against known reference landmarks or deterministically generates coordinates.
        """
        clean_q = query.strip().lower()
        if not clean_q:
            return None

        # Check known dictionary substrings (longest/most specific keys evaluated first)
        sorted_keys = sorted(KNOWN_LOCATIONS.keys(), key=len, reverse=True)
        for key in sorted_keys:
            if key in clean_q:
                lat, lng, addr, city, state, zip_code = KNOWN_LOCATIONS[key]
                return GeocodeResult(
                    formatted_address=addr,
                    coordinates=Coordinates(latitude=lat, longitude=lng),
                    place_id=f"mock_place_{key.replace(' ', '_')}",
                    city=city,
                    state=state,
                    postal_code=zip_code,
                    country="US",
                )

        # Deterministic coordinate generation based on string hash for arbitrary unmapped queries
        hasher = hashlib.md5(query.encode("utf-8")).hexdigest()
        offset_lat = (int(hasher[:4], 16) % 1000 - 500) / 10000.0
        offset_lng = (int(hasher[4:8], 16) % 1000 - 500) / 10000.0

        base_lat, base_lng = 37.774929, -122.419416  # San Francisco center
        sim_lat = round(base_lat + offset_lat, 6)
        sim_lng = round(base_lng + offset_lng, 6)

        return GeocodeResult(
            formatted_address=f"{query.title()}, USA",
            coordinates=Coordinates(latitude=sim_lat, longitude=sim_lng),
            place_id=f"mock_place_{hasher[:8]}",
            city="San Francisco",
            state="CA",
            postal_code="94102",
            country="US",
        )

    def reverse_geocode(self, lat: float, lng: float) -> GeocodeResult:
        """Find the nearest address for a coordinate point."""
        best_match = None
        min_dist = float("inf")

        for key, (k_lat, k_lng, addr, city, state, zip_code) in KNOWN_LOCATIONS.items():
            dist = haversine_distance_km(lat, lng, k_lat, k_lng)
            if dist < min_dist:
                min_dist = dist
                best_match = (addr, city, state, zip_code)

        if best_match and min_dist < 15.0:
            addr, city, state, zip_code = best_match
            formatted = f"Near {addr}"
        else:
            formatted = f"{lat:.4f}, {lng:.4f}, USA"
            city, state, zip_code = "Metropolitan Area", "US", "00000"

        return GeocodeResult(
            formatted_address=formatted,
            coordinates=Coordinates(latitude=round(lat, 6), longitude=round(lng, 6)),
            place_id=f"mock_rev_{abs(int(lat*1000))}_{abs(int(lng*1000))}",
            city=city,
            state=state,
            postal_code=zip_code,
            country="US",
        )

    def directions(
        self,
        origin: Coordinates,
        destination: Coordinates,
        mode: TravelMode = TravelMode.DRIVING,
        origin_name: str = "Origin",
        destination_name: str = "Destination",
    ) -> DirectionsResult:
        """Calculate turn-by-turn routing between origin and destination coordinates."""
        distance_km = haversine_distance_km(
            origin.latitude, origin.longitude, destination.latitude, destination.longitude
        )
        distance_miles = haversine_distance_miles(
            origin.latitude, origin.longitude, destination.latitude, destination.longitude
        )

        speed = SPEED_KMH.get(mode, 38.0)
        duration_hours = max(0.02, distance_km / speed)
        duration_seconds = int(duration_hours * 3600)

        # Duration formatting
        if duration_seconds < 60:
            duration_text = "1 min"
        elif duration_seconds < 3600:
            mins = math.ceil(duration_seconds / 60)
            duration_text = f"{mins} mins"
        else:
            hrs = duration_seconds // 3600
            mins = math.ceil((duration_seconds % 3600) / 60)
            duration_text = f"{hrs} hr {mins} mins" if mins > 0 else f"{hrs} hr"

        # Distance formatting
        if distance_miles < 0.1:
            dist_text = f"{int(distance_km * 1000)} m"
        else:
            dist_text = f"{distance_miles:.1f} mi"

        # Interpolate intermediate path coordinates for polyline
        num_waypoints = max(3, min(8, int(distance_km * 2) + 2))
        path_points: list[tuple[float, float]] = []
        route_coords: list[Coordinates] = []

        bearing = calculate_bearing(
            origin.latitude, origin.longitude, destination.latitude, destination.longitude
        )

        for i in range(num_waypoints + 1):
            fraction = i / float(num_waypoints)
            # Add subtle geographic curve to simulate street grid routing
            curve = math.sin(fraction * math.pi) * 0.003
            interp_lat = origin.latitude + (destination.latitude - origin.latitude) * fraction + curve
            interp_lng = origin.longitude + (destination.longitude - origin.longitude) * fraction - curve
            pt = (round(interp_lat, 5), round(interp_lng, 5))
            path_points.append(pt)
            route_coords.append(Coordinates(latitude=pt[0], longitude=pt[1]))

        overview_polyline = encode_polyline(path_points)

        # Synthesize turn-by-turn steps
        cardinal = (
            "North" if 315 <= bearing or bearing < 45
            else "East" if 45 <= bearing < 135
            else "South" if 135 <= bearing < 225
            else "West"
        )
        step_dist_meters = max(50, int((distance_km * 1000) / 4))
        step_dur_sec = max(20, duration_seconds // 4)

        steps = [
            RouteStep(
                instruction=f"Head {cardinal.lower()} toward the nearest arterial road",
                distance_meters=step_dist_meters,
                distance_text=f"{round(step_dist_meters * 0.000621371, 2)} mi",
                duration_seconds=step_dur_sec,
                duration_text=f"{max(1, step_dur_sec // 60)} min",
                start_location=route_coords[0],
                end_location=route_coords[1] if len(route_coords) > 1 else route_coords[0],
                travel_mode=mode,
            ),
            RouteStep(
                instruction=f"Turn right onto Main Boulevard and continue for {round(distance_miles * 0.5, 1)} mi",
                distance_meters=step_dist_meters * 2,
                distance_text=f"{round(distance_miles * 0.5, 1)} mi",
                duration_seconds=step_dur_sec * 2,
                duration_text=f"{max(1, (step_dur_sec * 2) // 60)} mins",
                start_location=route_coords[1] if len(route_coords) > 1 else route_coords[0],
                end_location=route_coords[-2] if len(route_coords) > 2 else route_coords[-1],
                travel_mode=mode,
            ),
            RouteStep(
                instruction=f"Turn left onto the commercial access drive toward {destination_name}",
                distance_meters=step_dist_meters,
                distance_text=f"{round(step_dist_meters * 0.000621371, 2)} mi",
                duration_seconds=step_dur_sec,
                duration_text=f"{max(1, step_dur_sec // 60)} min",
                start_location=route_coords[-2] if len(route_coords) > 2 else route_coords[0],
                end_location=route_coords[-1],
                travel_mode=mode,
            ),
            RouteStep(
                instruction=f"Arrive at {destination_name}. Destination will be on your right.",
                distance_meters=0,
                distance_text="0 ft",
                duration_seconds=0,
                duration_text="0 min",
                start_location=route_coords[-1],
                end_location=route_coords[-1],
                travel_mode=mode,
            ),
        ]

        return DirectionsResult(
            origin_address=origin_name if origin_name != "Origin" else f"{origin.latitude:.4f}, {origin.longitude:.4f}",
            destination_address=destination_name if destination_name != "Destination" else f"{destination.latitude:.4f}, {destination.longitude:.4f}",
            mode=mode,
            total_distance_km=distance_km,
            total_distance_miles=distance_miles,
            distance_text=dist_text,
            total_duration_seconds=duration_seconds,
            duration_text=duration_text,
            overview_polyline=overview_polyline,
            route_coordinates=route_coords,
            steps=steps,
        )
