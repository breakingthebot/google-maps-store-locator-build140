# src/services/traffic_engine.py
# Real-time traffic simulation, diurnal congestion curves, route segmentation, and predictive departure engine.
# Connects to: src/models/traffic.py, src/models/geo.py, src/models/directions.py, src/utils/distance.py, src/utils/polyline.py
# Created: 2026-09-06

from datetime import datetime, time
import math
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from src.models.directions import TravelMode
from src.models.geo import Coordinates
from src.models.traffic import (
    DepartureWindowPrediction,
    PredictiveDepartureResponse,
    TrafficCondition,
    TrafficModel,
    TrafficSegment,
)
from src.utils.distance import haversine_distance_km
from src.utils.polyline import encode_polyline

# Color mapping by traffic condition
CONDITION_COLORS: Dict[TrafficCondition, str] = {
    TrafficCondition.CLEAR: "#10b981",     # Emerald Green
    TrafficCondition.MODERATE: "#f59e0b",  # Amber
    TrafficCondition.HEAVY: "#f97316",     # Vivid Orange
    TrafficCondition.SEVERE: "#ef4444",    # Crimson Red
}


class TrafficEngine:
    """Enterprise traffic modeling engine calculating rush hour curves and predictive departure recommendations."""

    @staticmethod
    def parse_departure_time(departure_input: Optional[Union[str, int]]) -> Tuple[float, str, datetime]:
        """Parse arbitrary departure time input into (decimal_hour, formatted_label, datetime_obj).

        Supports 'now', presets ('morning_rush', 'midday', 'evening_rush', 'off_peak'),
        'HH:MM' time strings, ISO timestamps, and Unix epoch seconds.
        """
        now = datetime.now()

        if not departure_input or str(departure_input).strip().lower() in ("now", ""):
            dec_hour = now.hour + now.minute / 60.0
            label = f"Now ({now.strftime('%I:%M %p').lstrip('0')})"
            return dec_hour, label, now

        dep_str = str(departure_input).strip().lower()

        # Preset aliases
        presets = {
            "morning_rush": (8.5, "8:30 AM (Morning Rush)", 8, 30),
            "morning": (8.5, "8:30 AM (Morning Rush)", 8, 30),
            "rush": (17.5, "5:30 PM (Evening Rush)", 17, 30),
            "midday": (12.5, "12:30 PM (Midday)", 12, 30),
            "lunch": (12.5, "12:30 PM (Lunch)", 12, 30),
            "evening_rush": (17.5, "5:30 PM (Evening Rush)", 17, 30),
            "evening": (17.5, "5:30 PM (Evening Rush)", 17, 30),
            "off_peak": (21.5, "9:30 PM (Off-Peak Night)", 21, 30),
            "night": (22.0, "10:00 PM (Night)", 22, 0),
        }
        if dep_str in presets:
            dec_h, lbl, h, m = presets[dep_str]
            dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
            return dec_h, lbl, dt

        # Epoch seconds integer
        if dep_str.isdigit() and len(dep_str) >= 9:
            dt = datetime.fromtimestamp(int(dep_str))
            dec_hour = dt.hour + dt.minute / 60.0
            return dec_hour, dt.strftime("%I:%M %p").lstrip("0"), dt

        # HH:MM string (e.g. 08:30 or 17:15)
        hm_match = re.match(r"^(\d{1,2}):(\d{2})(?:\s*([ap]m))?$", dep_str)
        if hm_match:
            hours = int(hm_match.group(1))
            mins = int(hm_match.group(2))
            meridiem = hm_match.group(3)
            if meridiem:
                if meridiem == "pm" and hours < 12:
                    hours += 12
                elif meridiem == "am" and hours == 12:
                    hours = 0
            dt = now.replace(hour=hours, minute=mins, second=0, microsecond=0)
            dec_hour = hours + mins / 60.0
            return dec_hour, dt.strftime("%I:%M %p").lstrip("0"), dt

        # ISO format parser
        try:
            dt = datetime.fromisoformat(dep_str)
            dec_hour = dt.hour + dt.minute / 60.0
            return dec_hour, dt.strftime("%I:%M %p").lstrip("0"), dt
        except Exception:
            pass

        # Fallback to current time
        dec_hour = now.hour + now.minute / 60.0
        return dec_hour, f"Now ({now.strftime('%I:%M %p').lstrip('0')})", now

    @staticmethod
    def calculate_congestion_factor(
        decimal_hour: float,
        traffic_model: TrafficModel = TrafficModel.BEST_GUESS,
        mode: TravelMode = TravelMode.DRIVING,
    ) -> Tuple[float, TrafficCondition]:
        """Calculate traffic delay multiplier and condition from time of day and model heuristic.

        Non-driving modes (walking, cycling, transit) experience negligible road motor congestion.
        """
        if mode != TravelMode.DRIVING:
            return 1.0, TrafficCondition.CLEAR

        h = decimal_hour % 24.0

        # Base diurnal rush hour curve
        # Morning peak: 07:00 - 09:30 (peaks at 8:30 at 1.62x)
        # Evening peak: 16:30 - 18:45 (peaks at 17:30 at 1.78x)
        if 0.0 <= h < 6.0:
            raw_factor = 1.0
        elif 6.0 <= h < 7.0:
            raw_factor = 1.0 + (h - 6.0) * 0.15
        elif 7.0 <= h < 8.5:
            # Morning ramp
            progress = (h - 7.0) / 1.5
            raw_factor = 1.15 + math.sin(progress * (math.pi / 2)) * 0.47  # up to 1.62
        elif 8.5 <= h < 10.0:
            # Morning ease
            progress = (h - 8.5) / 1.5
            raw_factor = 1.62 - progress * 0.45  # down to 1.17
        elif 10.0 <= h < 11.5:
            raw_factor = 1.12
        elif 11.5 <= h < 13.5:
            # Lunch bump
            dist_to_lunch = abs(h - 12.5) / 1.0
            raw_factor = 1.28 - dist_to_lunch * 0.12  # ~1.16 - 1.28
        elif 13.5 <= h < 16.0:
            raw_factor = 1.18
        elif 16.0 <= h < 17.5:
            # Evening rush ramp
            progress = (h - 16.0) / 1.5
            raw_factor = 1.20 + math.sin(progress * (math.pi / 2)) * 0.58  # up to 1.78
        elif 17.5 <= h < 19.0:
            # Evening rush crest and ease
            progress = (h - 17.5) / 1.5
            raw_factor = 1.78 - progress * 0.48  # down to 1.30
        elif 19.0 <= h < 21.0:
            progress = (h - 19.0) / 2.0
            raw_factor = 1.30 - progress * 0.22  # down to 1.08
        else:
            raw_factor = 1.02

        # Traffic model heuristic adjustment
        if traffic_model == TrafficModel.OPTIMISTIC:
            adjusted_factor = 1.0 + (raw_factor - 1.0) * 0.70
        elif traffic_model == TrafficModel.PESSIMISTIC:
            adjusted_factor = 1.0 + (raw_factor - 1.0) * 1.35
        else:
            adjusted_factor = raw_factor

        adjusted_factor = round(max(1.0, adjusted_factor), 2)

        # Categorize condition
        if adjusted_factor <= 1.15:
            condition = TrafficCondition.CLEAR
        elif adjusted_factor <= 1.40:
            condition = TrafficCondition.MODERATE
        elif adjusted_factor <= 1.70:
            condition = TrafficCondition.HEAVY
        else:
            condition = TrafficCondition.SEVERE

        return adjusted_factor, condition

    @classmethod
    def segment_route_traffic(
        cls,
        route_coords: List[Coordinates],
        total_distance_meters: int,
        base_duration_seconds: int,
        overall_factor: float,
        overall_condition: TrafficCondition,
    ) -> List[TrafficSegment]:
        """Divide route coordinates into contiguous segments with varied congestion colors."""
        if len(route_coords) < 2:
            return []

        # Determine number of segments (2 to 5 based on route length)
        num_segments = max(2, min(5, len(route_coords) - 1))
        pts_per_segment = max(1, (len(route_coords) - 1) // num_segments)

        segments: List[TrafficSegment] = []
        for seg_idx in range(num_segments):
            start_i = seg_idx * pts_per_segment
            if seg_idx == num_segments - 1:
                end_i = len(route_coords) - 1
            else:
                end_i = min(len(route_coords) - 1, (seg_idx + 1) * pts_per_segment)

            slice_coords = route_coords[start_i : end_i + 1]
            if len(slice_coords) < 2:
                continue

            # Vary segment factor around overall factor to simulate real corridors
            # Core inner segments experience higher congestion than outer perimeter
            if num_segments >= 3 and 0 < seg_idx < num_segments - 1:
                seg_factor = round(min(2.1, overall_factor * 1.18), 2)
            else:
                seg_factor = round(max(1.0, overall_factor * 0.88), 2)

            if seg_factor <= 1.15:
                seg_cond = TrafficCondition.CLEAR
            elif seg_factor <= 1.40:
                seg_cond = TrafficCondition.MODERATE
            elif seg_factor <= 1.70:
                seg_cond = TrafficCondition.HEAVY
            else:
                seg_cond = TrafficCondition.SEVERE

            seg_pts = [(c.latitude, c.longitude) for c in slice_coords]
            poly = encode_polyline(seg_pts)

            seg_dist = max(10, int(total_distance_meters / num_segments))
            seg_dur = max(5, int((base_duration_seconds * seg_factor) / num_segments))

            segments.append(
                TrafficSegment(
                    segment_index=seg_idx,
                    start_location=slice_coords[0],
                    end_location=slice_coords[-1],
                    condition=seg_cond,
                    speed_factor=seg_factor,
                    polyline=poly,
                    color_hex=CONDITION_COLORS[seg_cond],
                    distance_meters=seg_dist,
                    duration_seconds=seg_dur,
                )
            )

        return segments

    @classmethod
    def predict_departure_matrix(
        cls,
        base_duration_seconds: int,
        travel_distance_km: float,
        origin_label: str = "Origin",
        destination_label: str = "Destination",
        traffic_model: TrafficModel = TrafficModel.BEST_GUESS,
        mode: TravelMode = TravelMode.DRIVING,
    ) -> PredictiveDepartureResponse:
        """Evaluate travel duration across key candidate departure windows throughout the day."""
        candidate_windows = [
            ("Early Morning (06:00 - 07:00)", 6.5, "06:30:00", "early_morning", "06:00 - 07:00"),
            ("Morning Rush (08:00 - 09:30)", 8.5, "08:30:00", "morning_rush", "08:00 - 09:30"),
            ("Midday Lunch (11:30 - 13:30)", 12.5, "12:30:00", "midday", "11:30 - 13:30"),
            ("Evening Rush (16:30 - 18:45)", 17.5, "17:30:00", "evening_rush", "16:30 - 18:45"),
            ("Off-Peak Night (20:30 - 23:00)", 21.5, "21:30:00", "off_peak", "20:30 - 23:00"),
        ]

        predictions: List[DepartureWindowPrediction] = []
        max_duration = 0
        min_duration = float("inf")
        worst_label = ""
        best_label = ""

        # First pass to compute durations
        raw_results = []
        for label, dec_h, time_part, w_key, t_range in candidate_windows:
            factor, cond = cls.calculate_congestion_factor(dec_h, traffic_model=traffic_model, mode=mode)
            dur_traffic_sec = int(round(base_duration_seconds * factor))
            delay_sec = max(0, dur_traffic_sec - base_duration_seconds)
            delay_mins = round(delay_sec / 60.0, 1)

            if dur_traffic_sec > max_duration:
                max_duration = dur_traffic_sec
                worst_label = label
            if dur_traffic_sec < min_duration:
                min_duration = dur_traffic_sec
                best_label = label

            raw_results.append((label, dec_h, time_part, w_key, t_range, factor, cond, dur_traffic_sec, delay_mins))

        today_str = datetime.now().strftime("%Y-%m-%d")

        for label, dec_h, time_part, w_key, t_range, factor, cond, dur_traffic_sec, delay_mins in raw_results:
            mins = math.ceil(dur_traffic_sec / 60.0)
            if mins < 60:
                dur_text = f"{mins} mins"
            else:
                h = mins // 60
                m = mins % 60
                dur_text = f"{h} hr {m} mins" if m > 0 else f"{h} hr"

            saved_vs_worst = round(max(0.0, (max_duration - dur_traffic_sec) / 60.0), 1)
            is_best = (dur_traffic_sec == min_duration)

            predictions.append(
                DepartureWindowPrediction(
                    departure_label=label,
                    departure_time_iso=f"{today_str}T{time_part}",
                    departure_hour=dec_h,
                    condition=cond,
                    duration_in_traffic_seconds=dur_traffic_sec,
                    duration_in_traffic_text=dur_text,
                    delay_minutes=delay_mins,
                    is_recommended=is_best,
                    time_saved_vs_worst_minutes=saved_vs_worst,
                    traffic_model=traffic_model,
                    window_key=w_key,
                    label=label,
                    time_range=t_range,
                    traffic_condition=cond.value,
                )
            )

        max_saved = round(max(0.0, (max_duration - min_duration) / 60.0), 1)

        base_mins = math.ceil(base_duration_seconds / 60.0)
        base_dur_text = f"{base_mins} mins" if base_mins < 60 else f"{base_mins // 60} hr {base_mins % 60} mins"

        best_pred = next((p for p in predictions if p.is_recommended), predictions[0] if predictions else None)
        worst_pred = max(predictions, key=lambda p: p.duration_in_traffic_seconds) if predictions else None

        return PredictiveDepartureResponse(
            origin_label=origin_label,
            destination_label=destination_label,
            base_duration_seconds=base_duration_seconds,
            base_duration_text=base_dur_text,
            travel_distance_km=round(travel_distance_km, 2),
            travel_distance_miles=round(travel_distance_km * 0.621371, 2),
            traffic_model=traffic_model,
            best_departure_time=best_label,
            worst_departure_time=worst_label,
            max_time_saved_minutes=max_saved,
            windows=predictions,
            predictions=predictions,
            best_window=best_pred,
            worst_window=worst_pred,
            max_time_saved_seconds=int(round(max_saved * 60)),
        )


    @classmethod
    def get_arterial_traffic_overlay(cls, decimal_hour: Optional[float] = None) -> List[Dict[str, Any]]:
        """Generate major city arterial traffic corridors for map visual layer overlay."""
        if decimal_hour is None:
            now = datetime.now()
            decimal_hour = now.hour + now.minute / 60.0

        factor, overall_cond = cls.calculate_congestion_factor(decimal_hour)

        # Reference arterial street corridors in metropolitan area
        corridors = [
            {
                "name": "Market St Commercial Arterial",
                "start": (37.7941, -122.3956),
                "end": (37.7705, -122.4269),
                "congestion_bias": 1.25,
            },
            {
                "name": "Mission St Transit Corridor",
                "start": (37.7892, -122.3995),
                "end": (37.7471, -122.4185),
                "congestion_bias": 1.15,
            },
            {
                "name": "The Embarcadero Waterfront",
                "start": (37.8080, -122.4177),
                "end": (37.7785, -122.3892),
                "congestion_bias": 0.90,
            },
            {
                "name": "Van Ness Ave Cross-Town",
                "start": (37.8052, -122.4243),
                "end": (37.7701, -122.4198),
                "congestion_bias": 1.30,
            },
            {
                "name": "Geary Expressway",
                "start": (37.7869, -122.4080),
                "end": (37.7801, -122.4831),
                "congestion_bias": 1.10,
            },
            {
                "name": "Highway 101 Bayshore Freeway",
                "start": (37.7720, -122.4050),
                "end": (37.7310, -122.4020),
                "congestion_bias": 1.35,
            },
        ]

        results = []
        for c in corridors:
            corridor_factor = round(factor * c["congestion_bias"], 2)
            if corridor_factor <= 1.15:
                cond = TrafficCondition.CLEAR
            elif corridor_factor <= 1.40:
                cond = TrafficCondition.MODERATE
            elif corridor_factor <= 1.70:
                cond = TrafficCondition.HEAVY
            else:
                cond = TrafficCondition.SEVERE

            poly = encode_polyline([c["start"], c["end"]])
            results.append(
                {
                    "name": c["name"],
                    "start_lat": c["start"][0],
                    "start_lng": c["start"][1],
                    "end_lat": c["end"][0],
                    "end_lng": c["end"][1],
                    "condition": cond.value,
                    "color_hex": CONDITION_COLORS[cond],
                    "speed_factor": corridor_factor,
                    "polyline": poly,
                }
            )

        return results


# Module-level convenience aliases
parse_departure_time = TrafficEngine.parse_departure_time
calculate_congestion_factor = TrafficEngine.calculate_congestion_factor
segment_route_traffic = TrafficEngine.segment_route_traffic
predict_departure_matrix = TrafficEngine.predict_departure_matrix
get_arterial_traffic_overlay = TrafficEngine.get_arterial_traffic_overlay
