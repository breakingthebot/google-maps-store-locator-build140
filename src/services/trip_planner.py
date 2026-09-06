# src/services/trip_planner.py
# Multi-stop trip planner orchestrating store retrieval, TSP route optimization, and turn-by-turn itinerary generation.
# Connects to: src/models/trip.py, src/models/geo.py, src/models/directions.py, src/services/store_repository.py, src/utils/optimizer.py
# Created: 2026-09-06

import asyncio
import logging
import math
import re
from typing import Any, List, Optional, Tuple, Union
from src.config import settings
from src.models.directions import DirectionsResult, RouteStep, TravelMode
from src.models.geo import Coordinates, GeocodeResult
from src.models.trip import (
    TripLeg,
    TripPlanRequest,
    TripPlanResponse,
    TripSavings,
    WaypointNode,
)
from src.models.traffic import (
    PredictiveDepartureResponse,
    TrafficCondition,
    TrafficModel,
)
from src.services.google_maps import GoogleMapsService
from src.services.mock_maps import MockGoogleMapsService
from src.services.store_repository import StoreRepository
from src.services.trip_exporter import TripExporter
from src.utils.distance import haversine_distance_km, haversine_distance_miles
from src.utils.optimizer import compute_distance_matrix, compute_tour_distance, optimize_route
from src.utils.polyline import decode_polyline, encode_polyline

logger = logging.getLogger("store_locator.trip_planner")


class TripPlannerService:
    """Orchestrates multi-stop trip routing with Travelling Salesperson (TSP) waypoint optimization."""

    def __init__(
        self,
        store_repo: Optional[StoreRepository] = None,
        maps_service: Optional[Any] = None,
    ) -> None:
        self.store_repo = store_repo or StoreRepository()
        if maps_service is not None:
            self.maps_service = maps_service
        else:
            self.maps_service = GoogleMapsService()

    async def _geocode_async(self, address: str) -> Optional[GeocodeResult]:
        """Async-safe wrapper supporting both async and sync geocode implementations."""
        res = self.maps_service.geocode(address)
        if hasattr(res, "__await__"):
            return await res
        return res

    async def _directions_async(
        self,
        origin: Coordinates,
        destination: Coordinates,
        mode: TravelMode,
        origin_name: str,
        destination_name: str,
        departure_time: Optional[Union[str, int]] = None,
        traffic_model: TrafficModel = TrafficModel.BEST_GUESS,
    ) -> DirectionsResult:
        """Async-safe wrapper supporting both async and sync directions implementations with traffic modeling."""
        res = self.maps_service.directions(
            origin=origin,
            destination=destination,
            mode=mode,
            origin_name=origin_name,
            destination_name=destination_name,
            departure_time=departure_time,
            traffic_model=traffic_model,
        )
        if hasattr(res, "__await__"):
            return await res
        return res

    async def _resolve_origin(self, origin_str: str, explicit_coords: Optional[Coordinates] = None) -> Tuple[Coordinates, str]:
        """Resolve origin coordinates and display label from string or explicit coordinates."""
        if explicit_coords:
            return explicit_coords, origin_str.strip() or "Custom Origin"

        # Check if query is raw "latitude,longitude"
        coord_match = re.match(r"^([-+]?\d{1,2}(?:\.\d+)?),\s*([-+]?\d{1,3}(?:\.\d+)?)$", origin_str.strip())
        if coord_match:
            lat, lng = float(coord_match.group(1)), float(coord_match.group(2))
            return Coordinates(latitude=lat, longitude=lng), f"{lat:.4f}, {lng:.4f}"

        # Geocode via maps service
        geocode_res = await self._geocode_async(origin_str)
        if geocode_res:
            return geocode_res.coordinates, geocode_res.formatted_address

        # Fallback to default location
        logger.warning(f"Could not geocode origin '{origin_str}'. Falling back to default center.")
        return (
            Coordinates(latitude=settings.default_latitude, longitude=settings.default_longitude),
            f"{origin_str} (Default SF Coordinates)",
        )

    async def plan_trip(self, request: TripPlanRequest) -> TripPlanResponse:
        """Calculate an optimized multi-stop itinerary visiting all requested stores with traffic modeling.

        Args:
            request: TripPlanRequest specifying origin, store_ids, round_trip, optimize flag, and traffic settings.

        Returns:
            TripPlanResponse with sequenced stops, leg-by-leg navigation, cumulative savings, and traffic delays.

        Raises:
            ValueError: If fewer than 2 stores are provided or if any store ID does not exist.
        """
        if len(request.store_ids) < 2:
            raise ValueError("Trip planning requires at least 2 store destinations.")

        # 1. Resolve Origin
        origin_coords, origin_label = await self._resolve_origin(request.origin, request.origin_coordinates)

        # 2. Fetch and Validate Stores
        stores = []
        for sid in request.store_ids:
            store = self.store_repo.get_by_id(sid)
            if not store:
                raise ValueError(f"Store with ID {sid} not found in database.")
            stores.append(store)

        # 3. Create Node Candidates
        # Node 0 is always the starting origin
        origin_node = WaypointNode(
            sequence_index=0,
            name="Trip Origin",
            address=origin_label,
            coordinates=origin_coords,
            store_id=None,
            is_origin=True,
            is_destination=False,
        )

        candidate_nodes = [origin_node]
        for s in stores:
            candidate_nodes.append(
                WaypointNode(
                    sequence_index=0,
                    name=s.name,
                    address=s.full_address,
                    coordinates=Coordinates(latitude=s.latitude, longitude=s.longitude),
                    store_id=s.id,
                    is_origin=False,
                    is_destination=False,
                )
            )

        coords = [(n.coordinates.latitude, n.coordinates.longitude) for n in candidate_nodes]

        # 4. TSP Waypoint Optimization
        if request.optimize:
            best_tour, opt_distance, naive_distance = optimize_route(coords, round_trip=request.round_trip)
        else:
            dist_matrix = compute_distance_matrix(coords)
            best_tour = list(range(len(candidate_nodes)))
            opt_distance = compute_tour_distance(best_tour, dist_matrix, round_trip=request.round_trip)
            naive_distance = opt_distance

        # best_tour is a permutation of indices [0, ...], where index 0 is origin
        # 5. Build Chronological Stops
        ordered_stops: List[WaypointNode] = []
        ordered_store_ids: List[int] = []

        for seq_idx, node_idx in enumerate(best_tour):
            node_copy = candidate_nodes[node_idx].model_copy()
            node_copy.sequence_index = seq_idx
            if node_copy.store_id is not None:
                ordered_store_ids.append(node_copy.store_id)
            ordered_stops.append(node_copy)

        # If round-trip, add return stop back to origin
        if request.round_trip:
            return_node = WaypointNode(
                sequence_index=len(ordered_stops),
                name=f"{origin_label} (Return)",
                address=origin_label,
                coordinates=origin_coords,
                store_id=None,
                is_origin=False,
                is_destination=True,
            )
            ordered_stops.append(return_node)
            destination_label = origin_label
        else:
            ordered_stops[-1].is_destination = True
            destination_label = ordered_stops[-1].name

        # 6. Generate Route Legs
        legs: List[TripLeg] = []
        total_distance_km = 0.0
        total_duration_sec = 0
        total_traffic_sec = 0
        total_delay_sec = 0
        all_polyline_coords: List[Tuple[float, float]] = []

        for leg_idx in range(len(ordered_stops) - 1):
            start = ordered_stops[leg_idx]
            end = ordered_stops[leg_idx + 1]

            # Route using maps service with traffic parameters
            dir_res = await self._directions_async(
                origin=start.coordinates,
                destination=end.coordinates,
                mode=request.travel_mode,
                origin_name=start.name,
                destination_name=end.name,
                departure_time=request.departure_time,
                traffic_model=request.traffic_model,
            )

            leg_km = round(dir_res.total_distance_km, 2)
            leg_miles = round(dir_res.total_distance_miles, 2)
            leg_dur_min = round(dir_res.total_duration_seconds / 60.0, 1)

            total_distance_km += leg_km
            total_duration_sec += dir_res.total_duration_seconds

            leg_traffic_sec = dir_res.duration_in_traffic_seconds if dir_res.duration_in_traffic_seconds is not None else dir_res.total_duration_seconds
            total_traffic_sec += leg_traffic_sec
            leg_delay_sec = dir_res.traffic_delay_seconds
            total_delay_sec += leg_delay_sec

            leg_traffic_mins = round(leg_traffic_sec / 60.0, 1)
            leg_delay_mins = round(leg_delay_sec / 60.0, 1)

            # Decode polyline coordinates to merge into composite tour polyline
            if dir_res.overview_polyline:
                decoded_pts = decode_polyline(dir_res.overview_polyline)
                if not all_polyline_coords:
                    all_polyline_coords.extend(decoded_pts)
                else:
                    # Avoid duplicate overlapping joint coordinate
                    all_polyline_coords.extend(decoded_pts[1:])

            legs.append(
                TripLeg(
                    leg_index=leg_idx,
                    start_node=start,
                    end_node=end,
                    distance_km=leg_km,
                    distance_miles=leg_miles,
                    distance_text=dir_res.distance_text,
                    duration_minutes=leg_dur_min,
                    duration_text=dir_res.duration_text,
                    duration_in_traffic_minutes=leg_traffic_mins,
                    duration_in_traffic_text=dir_res.duration_in_traffic_text or dir_res.duration_text,
                    traffic_condition=dir_res.traffic_condition,
                    traffic_delay_minutes=leg_delay_mins,
                    steps=dir_res.steps,
                    polyline=dir_res.overview_polyline,
                    traffic_segments=dir_res.traffic_segments,
                )
            )

        # 7. Calculate Totals & Formatting
        total_distance_km = round(total_distance_km, 2)
        total_distance_miles = round(total_distance_km * 0.621371, 2)
        total_duration_mins = round(total_duration_sec / 60.0, 1)
        total_traffic_mins = round(total_traffic_sec / 60.0, 1)
        total_delay_mins = round(total_delay_sec / 60.0, 1)

        if total_distance_miles < 0.1:
            total_dist_text = f"{int(total_distance_km * 1000)} m"
        else:
            total_dist_text = f"{total_distance_miles:.1f} mi"

        if total_duration_sec < 60:
            total_dur_text = "1 min"
        elif total_duration_sec < 3600:
            total_dur_text = f"{math.ceil(total_duration_mins)} mins"
        else:
            hours = int(total_duration_mins // 60)
            mins = int(math.ceil(total_duration_mins % 60))
            total_dur_text = f"{hours} hr {mins} mins" if mins > 0 else f"{hours} hr"

        if total_traffic_sec < 60:
            total_traffic_text = "1 min"
        elif total_traffic_sec < 3600:
            total_traffic_text = f"{math.ceil(total_traffic_mins)} mins"
        else:
            t_hours = int(total_traffic_mins // 60)
            t_mins = int(math.ceil(total_traffic_mins % 60))
            total_traffic_text = f"{t_hours} hr {t_mins} mins" if t_mins > 0 else f"{t_hours} hr"

        # Overall trip traffic condition
        overall_factor = total_traffic_sec / max(1, total_duration_sec)
        from src.models.traffic import TrafficCondition
        if overall_factor <= 1.15:
            overall_traffic_cond = TrafficCondition.CLEAR
        elif overall_factor <= 1.40:
            overall_traffic_cond = TrafficCondition.MODERATE
        elif overall_factor <= 1.70:
            overall_traffic_cond = TrafficCondition.HEAVY
        else:
            overall_traffic_cond = TrafficCondition.SEVERE

        # Overview polyline from accumulated coordinates
        overview_polyline = encode_polyline(all_polyline_coords) if all_polyline_coords else ""

        # 8. Compute Quantified Savings
        savings = None
        if request.optimize and naive_distance > (opt_distance + 0.05):
            saved_km = round(naive_distance - opt_distance, 2)
            saved_miles = round(saved_km * 0.621371, 2)
            pct_saved = round((saved_km / naive_distance) * 100, 1)
            # Estimate time saved based on average transit speed (38 km/h)
            mins_saved = round((saved_km / 38.0) * 60.0, 1)
            savings = TripSavings(
                naive_distance_km=round(naive_distance, 2),
                optimized_distance_km=round(opt_distance, 2),
                distance_saved_km=saved_km,
                distance_saved_miles=saved_miles,
                percentage_distance_saved=pct_saved,
                estimated_minutes_saved=mins_saved,
            )

        plan_res = TripPlanResponse(
            origin_label=origin_label,
            destination_label=destination_label,
            round_trip=request.round_trip,
            travel_mode=request.travel_mode,
            optimized=request.optimize,
            optimized_store_ids=ordered_store_ids,
            stops=ordered_stops,
            legs=legs,
            total_distance_km=total_distance_km,
            total_distance_miles=total_distance_miles,
            total_distance_text=total_dist_text,
            total_duration_minutes=total_duration_mins,
            total_duration_text=total_dur_text,
            total_duration_in_traffic_minutes=total_traffic_mins,
            total_duration_in_traffic_text=total_traffic_text,
            total_traffic_delay_minutes=total_delay_mins,
            traffic_condition=overall_traffic_cond,
            departure_time=request.departure_time,
            traffic_model=request.traffic_model,
            overview_polyline=overview_polyline,
            savings=savings,
        )
        plan_res.google_maps_url = TripExporter.generate_google_maps_url(plan_res)
        return plan_res

    async def predict_departures(
        self,
        origin_str: str,
        destination_store_id: Optional[int] = None,
        store_ids: Optional[List[int]] = None,
        traffic_model: TrafficModel = TrafficModel.BEST_GUESS,
        mode: TravelMode = TravelMode.DRIVING,
        round_trip: bool = True,
        optimize: bool = True,
    ) -> PredictiveDepartureResponse:
        """Analyze departure times throughout the day and calculate optimal departure windows for single destination or multi-stop trip."""
        from src.services.traffic_engine import TrafficEngine

        if store_ids and len(store_ids) >= 2:
            plan_req = TripPlanRequest(
                origin=origin_str,
                store_ids=store_ids,
                round_trip=round_trip,
                optimize=optimize,
                travel_mode=mode,
                departure_time=None,
                traffic_model=traffic_model,
            )
            trip_res = await self.plan_trip(plan_req)
            return TrafficEngine.predict_departure_matrix(
                base_duration_seconds=int(round(trip_res.total_duration_minutes * 60)),
                travel_distance_km=trip_res.total_distance_km,
                origin_label=trip_res.origin_label,
                destination_label=f"{len(store_ids)} Stops Itinerary",
                traffic_model=traffic_model,
                mode=mode,
            )
        elif destination_store_id is not None:
            store = self.store_repo.get_by_id(destination_store_id)
            if not store:
                raise ValueError(f"Store ID {destination_store_id} not found.")

            origin_coords, origin_label = await self._resolve_origin(origin_str)

            # Get baseline route without traffic
            dir_res = await self._directions_async(
                origin=origin_coords,
                destination=store.coordinates,
                mode=mode,
                origin_name=origin_label,
                destination_name=store.name,
                departure_time=None,
            )

            return TrafficEngine.predict_departure_matrix(
                base_duration_seconds=dir_res.total_duration_seconds,
                travel_distance_km=dir_res.total_distance_km,
                origin_label=origin_label,
                destination_label=store.name,
                traffic_model=traffic_model,
                mode=mode,
            )
        else:
            raise ValueError("Must provide either destination_store_id or store_ids.")


