# src/services/google_maps.py
# Production Google Maps Platform HTTP client with retry policies, key masking, and mock engine fallback.
# Connects to: src/config.py, src/models/geo.py, src/models/directions.py, src/services/mock_maps.py
# Created: 2026-09-06

import asyncio
import logging
from typing import Any, Optional, Union
import httpx
from src.config import settings
from src.models.directions import DirectionsResult, RouteStep, TravelMode
from src.models.geo import Coordinates, GeocodeResult
from src.models.traffic import TrafficModel
from src.services.mock_maps import MockGoogleMapsService
from src.utils.polyline import decode_polyline

logger = logging.getLogger("store_locator.google_maps")

GEOCODE_API_URL = "https://maps.googleapis.com/maps/api/geocode/json"
DIRECTIONS_API_URL = "https://maps.googleapis.com/maps/api/directions/json"
PLACE_DETAILS_API_URL = "https://maps.googleapis.com/maps/api/place/details/json"


class GoogleMapsService:
    """Unified Google Maps Platform client supporting Geocoding and Directions APIs."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or settings.google_maps_api_key
        self.mock_service = MockGoogleMapsService()
        self.is_live = bool(self.api_key and self.api_key.strip())
        logger.info("GoogleMapsService initialized. Live mode: %s", self.is_live)

    async def _execute_http_request(
        self, url: str, params: dict[str, Any], max_attempts: int = 3
    ) -> dict[str, Any]:
        """Execute external HTTP request with exponential backoff on 5xx/429 status codes."""
        req_params = dict(params)
        if self.api_key:
            req_params["key"] = self.api_key

        safe_params = {k: ("***REDACTED***" if k == "key" else v) for k, v in req_params.items()}

        async with httpx.AsyncClient(timeout=10.0) as client:
            for attempt in range(1, max_attempts + 1):
                try:
                    logger.debug("Requesting %s with params %s (attempt %d)", url, safe_params, attempt)
                    response = await client.get(url, params=req_params)

                    if response.status_code == 200:
                        data = response.json()
                        status = data.get("status")
                        if status in ("OK", "ZERO_RESULTS"):
                            return data
                        logger.warning("Google Maps API returned non-OK status: %s", status)
                        return data

                    # Handle retryable server errors
                    if response.status_code in (429, 500, 502, 503, 504):
                        if attempt < max_attempts:
                            sleep_time = 0.5 * (2 ** (attempt - 1))
                            logger.warning(
                                "Transient HTTP %d error from Google Maps. Retrying in %.2fs",
                                response.status_code,
                                sleep_time,
                            )
                            await asyncio.sleep(sleep_time)
                            continue

                    response.raise_for_status()
                except httpx.RequestError as exc:
                    if attempt < max_attempts:
                        await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
                        continue
                    logger.error("HTTP request to Google Maps failed permanently: %s", exc)
                    raise

        raise RuntimeError("Failed to obtain response from Google Maps API")

    async def geocode(self, address: str) -> Optional[GeocodeResult]:
        """Geocode an address or postal code to Coordinates."""
        if not self.is_live:
            return self.mock_service.geocode(address)

        try:
            data = await self._execute_http_request(GEOCODE_API_URL, {"address": address})
            results = data.get("results", [])
            if not results:
                return None

            first = results[0]
            loc = first["geometry"]["location"]
            coords = Coordinates(latitude=loc["lat"], longitude=loc["lng"])

            city, state, postal_code, country = "", "", "", "US"
            for comp in first.get("address_components", []):
                types = comp.get("types", [])
                if "locality" in types:
                    city = comp.get("long_name", "")
                elif "administrative_area_level_1" in types:
                    state = comp.get("short_name", "")
                elif "postal_code" in types:
                    postal_code = comp.get("long_name", "")
                elif "country" in types:
                    country = comp.get("short_name", "US")

            return GeocodeResult(
                formatted_address=first.get("formatted_address", address),
                coordinates=coords,
                place_id=first.get("place_id"),
                city=city,
                state=state,
                postal_code=postal_code,
                country=country,
            )
        except Exception as exc:
            logger.warning("Live geocoding failed (%s). Falling back to mock engine.", exc)
            return self.mock_service.geocode(address)

    async def reverse_geocode(self, lat: float, lng: float) -> Optional[GeocodeResult]:
        """Reverse geocode coordinates into a human-readable address."""
        if not self.is_live:
            return self.mock_service.reverse_geocode(lat, lng)

        try:
            data = await self._execute_http_request(GEOCODE_API_URL, {"latlng": f"{lat},{lng}"})
            results = data.get("results", [])
            if not results:
                return self.mock_service.reverse_geocode(lat, lng)

            first = results[0]
            return GeocodeResult(
                formatted_address=first.get("formatted_address", f"{lat:.4f}, {lng:.4f}"),
                coordinates=Coordinates(latitude=lat, longitude=lng),
                place_id=first.get("place_id"),
                country="US",
            )
        except Exception as exc:
            logger.warning("Live reverse geocoding failed (%s). Using mock engine.", exc)
            return self.mock_service.reverse_geocode(lat, lng)

    async def directions(
        self,
        origin: Coordinates,
        destination: Coordinates,
        mode: TravelMode = TravelMode.DRIVING,
        origin_name: str = "Origin",
        destination_name: str = "Destination",
        departure_time: Optional[Union[str, int]] = None,
        traffic_model: TrafficModel = TrafficModel.BEST_GUESS,
    ) -> DirectionsResult:
        """Fetch turn-by-turn navigation directions with optional traffic modeling between two points."""
        from src.services.traffic_engine import TrafficEngine

        if not self.is_live:
            return self.mock_service.directions(
                origin=origin,
                destination=destination,
                mode=mode,
                origin_name=origin_name,
                destination_name=destination_name,
                departure_time=departure_time,
                traffic_model=traffic_model,
            )

        try:
            params: dict[str, Any] = {
                "origin": f"{origin.latitude},{origin.longitude}",
                "destination": f"{destination.latitude},{destination.longitude}",
                "mode": mode.value,
            }
            if departure_time is not None:
                if str(departure_time).strip().lower() == "now":
                    params["departure_time"] = "now"
                else:
                    dec_h, _, dt = TrafficEngine.parse_departure_time(departure_time)
                    params["departure_time"] = int(dt.timestamp())
                if mode == TravelMode.DRIVING:
                    params["traffic_model"] = traffic_model.value

            data = await self._execute_http_request(DIRECTIONS_API_URL, params)
            routes = data.get("routes", [])
            if not routes:
                return self.mock_service.directions(
                    origin=origin,
                    destination=destination,
                    mode=mode,
                    origin_name=origin_name,
                    destination_name=destination_name,
                    departure_time=departure_time,
                    traffic_model=traffic_model,
                )

            route = routes[0]
            leg = route["legs"][0]

            dist_meters = leg["distance"]["value"]
            dist_km = round(dist_meters / 1000.0, 2)
            dist_miles = round(dist_meters * 0.000621371, 2)
            dur_seconds = leg["duration"]["value"]
            dur_text = leg["duration"]["text"]

            # Parse Google duration_in_traffic if returned
            dur_in_traffic_sec = None
            dur_traffic_text = None
            traffic_delay_sec = 0
            traffic_delay_text = "0 min"

            if "duration_in_traffic" in leg:
                dur_in_traffic_sec = leg["duration_in_traffic"]["value"]
                dur_traffic_text = leg["duration_in_traffic"]["text"]
                traffic_delay_sec = max(0, dur_in_traffic_sec - dur_seconds)
                del_mins = round(traffic_delay_sec / 60)
                traffic_delay_text = f"+{del_mins} mins" if del_mins > 1 else f"+{del_mins} min" if del_mins == 1 else "0 min"

            overview_polyline = route["overview_polyline"]["points"]
            route_coords = decode_polyline(overview_polyline)

            # Determine traffic condition
            factor = (dur_in_traffic_sec / max(1, dur_seconds)) if dur_in_traffic_sec else 1.0
            from src.models.traffic import TrafficCondition
            if factor <= 1.15:
                traffic_cond = TrafficCondition.CLEAR
            elif factor <= 1.40:
                traffic_cond = TrafficCondition.MODERATE
            elif factor <= 1.70:
                traffic_cond = TrafficCondition.HEAVY
            else:
                traffic_cond = TrafficCondition.SEVERE

            traffic_segments = TrafficEngine.segment_route_traffic(
                route_coords=route_coords,
                total_distance_meters=dist_meters,
                base_duration_seconds=dur_seconds,
                overall_factor=factor,
                overall_condition=traffic_cond,
            )

            steps: list[RouteStep] = []
            for s in leg.get("steps", []):
                raw_html = s.get("html_instructions", "")
                import re
                clean_instruction = re.sub("<[^<]+?>", " ", raw_html).strip()

                steps.append(
                    RouteStep(
                        instruction=clean_instruction,
                        distance_meters=s["distance"]["value"],
                        distance_text=s["distance"]["text"],
                        duration_seconds=s["duration"]["value"],
                        duration_text=s["duration"]["text"],
                        start_location=Coordinates(
                            latitude=s["start_location"]["lat"],
                            longitude=s["start_location"]["lng"],
                        ),
                        end_location=Coordinates(
                            latitude=s["end_location"]["lat"],
                            longitude=s["end_location"]["lng"],
                        ),
                        travel_mode=mode,
                        traffic_condition=traffic_cond,
                    )
                )

            return DirectionsResult(
                origin_address=leg.get("start_address", origin_name),
                destination_address=leg.get("end_address", destination_name),
                mode=mode,
                total_distance_km=dist_km,
                total_distance_miles=dist_miles,
                distance_text=leg["distance"]["text"],
                total_duration_seconds=dur_seconds,
                duration_text=dur_text,
                duration_in_traffic_seconds=dur_in_traffic_sec,
                duration_in_traffic_text=dur_traffic_text,
                traffic_condition=traffic_cond,
                traffic_delay_seconds=traffic_delay_sec,
                traffic_delay_text=traffic_delay_text,
                overview_polyline=overview_polyline,
                route_coordinates=route_coords,
                steps=steps,
                traffic_segments=traffic_segments,
            )
        except Exception as exc:
            logger.warning("Live directions API failed (%s). Using mock engine.", exc)
            return self.mock_service.directions(
                origin=origin,
                destination=destination,
                mode=mode,
                origin_name=origin_name,
                destination_name=destination_name,
                departure_time=departure_time,
                traffic_model=traffic_model,
            )
