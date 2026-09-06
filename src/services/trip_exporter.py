# src/services/trip_exporter.py
# Exporter service generating Google Maps mobile deep links, GPX 1.1 route files, and CSV driver manifests.
# Connects to: src/models/trip.py, src/api/routes.py, src/cli/main.py
# Created: 2026-09-06

import csv
import io
import urllib.parse
from datetime import datetime
from xml.sax.saxutils import escape as xml_escape

from src.models.trip import TripPlan


class TripExporter:
    """Service providing multi-format route export capabilities."""

    @staticmethod
    def generate_google_maps_url(plan: TripPlan) -> str:
        """Construct an official Google Maps Universal Cross-Platform Navigation URL.

        Conforms to Google Maps URL API specs:
        https://developers.google.com/maps/documentation/urls/get-started#directions-action

        Args:
            plan: The solved TripPlan containing sequenced stops.

        Returns:
            Fully encoded https://www.google.com/maps/dir/?api=1 URL.
        """
        if not plan.stops or len(plan.stops) < 2:
            return "https://www.google.com/maps"

        origin_stop = plan.stops[0]
        dest_stop = plan.stops[-1]
        intermediate_stops = plan.stops[1:-1]

        origin_param = f"{origin_stop.coordinates.latitude:.6f},{origin_stop.coordinates.longitude:.6f}"
        dest_param = f"{dest_stop.coordinates.latitude:.6f},{dest_stop.coordinates.longitude:.6f}"

        mode_val = plan.travel_mode.value if hasattr(plan.travel_mode, "value") else str(plan.travel_mode)
        params = {
            "api": "1",
            "origin": origin_param,
            "destination": dest_param,
            "travelmode": mode_val,
        }

        if intermediate_stops:
            waypoints = "|".join(f"{s.coordinates.latitude:.6f},{s.coordinates.longitude:.6f}" for s in intermediate_stops)
            params["waypoints"] = waypoints

        query_string = urllib.parse.urlencode(params)
        return f"https://www.google.com/maps/dir/?{query_string}"

    @staticmethod
    def generate_gpx(plan: TripPlan) -> str:
        """Generate a valid GPS Exchange Format (GPX 1.1) XML document.

        Compatible with Garmin units, handheld GPS receivers, OsmAnd, and fitness devices.

        Args:
            plan: The solved TripPlan entity.

        Returns:
            XML string formatted as GPX 1.1.
        """
        try:
            from datetime import UTC
            created_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ImportError:
            created_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<gpx version="1.1" creator="Google Maps Store Locator &amp; Trip Planner"',
            '     xmlns="http://www.topografix.com/GPX/1/1"',
            '     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
            '     xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd">',
            f'  <metadata>',
            f'    <name>Optimized Trip: {xml_escape(plan.origin_label)}</name>',
            f'    <desc>Total Distance: {plan.total_distance_text}, Travel Time: {plan.total_duration_text}</desc>',
            f'    <time>{created_iso}</time>',
            f'  </metadata>',
        ]

        # Waypoints for each stop
        for stop in plan.stops:
            role = "Origin" if stop.is_origin else ("Return" if stop.is_destination and stop.store_id is None else f"Stop {stop.sequence_index}")
            lines.append(f'  <wpt lat="{stop.coordinates.latitude:.6f}" lon="{stop.coordinates.longitude:.6f}">')
            lines.append(f'    <name>{xml_escape(stop.name)} ({role})</name>')
            lines.append(f'    <desc>{xml_escape(stop.address)}</desc>')
            lines.append(f'    <sym>Shop</sym>')
            lines.append(f'  </wpt>')

        # Route elements
        lines.append('  <rte>')
        lines.append(f'    <name>Optimized Multi-Stop Route</name>')
        lines.append(f'    <number>1</number>')

        for stop in plan.stops:
            lines.append(f'    <rtept lat="{stop.coordinates.latitude:.6f}" lon="{stop.coordinates.longitude:.6f}">')
            lines.append(f'      <name>{xml_escape(stop.name)}</name>')
            lines.append(f'    </rtept>')

        lines.append('  </rte>')
        lines.append('</gpx>')

        return "\n".join(lines)

    @staticmethod
    def generate_csv(plan: TripPlan) -> str:
        """Generate a CSV driver itinerary manifest.

        Args:
            plan: The solved TripPlan entity.

        Returns:
            CSV string formatted with column headers.
        """
        output = io.StringIO()
        writer = csv.writer(output, lineterminator="\n")

        try:
            from datetime import UTC
            created_str = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        except ImportError:
            created_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        # Header summary
        writer.writerow(["# Optimized Store Delivery & Visit Manifest"])
        writer.writerow(["# Created At", created_str])
        writer.writerow(["# Total Distance", plan.total_distance_text])
        writer.writerow(["# Estimated Travel Time", plan.total_duration_text])
        writer.writerow(["# Total Stops", len(plan.stops)])
        writer.writerow([])

        # Table header
        writer.writerow([
            "Stop #",
            "Stop Type",
            "Store / Location Name",
            "Full Address",
            "Phone",
            "Leg Distance (mi)",
            "Leg Duration",
            "Signature / Completed",
        ])

        for i, stop in enumerate(plan.stops):
            stop_type = "Departure Origin" if stop.is_origin else ("Final Destination" if stop.is_destination else f"Waypoint {stop.sequence_index}")
            leg_dist = f"{plan.legs[i-1].distance_miles:.1f} mi" if i > 0 and i - 1 < len(plan.legs) else "0.0 mi"
            leg_dur = plan.legs[i-1].duration_text if i > 0 and i - 1 < len(plan.legs) else "0 min"
            phone_str = getattr(stop, "phone", None) or "N/A"

            writer.writerow([
                stop.sequence_index,
                stop_type,
                stop.name,
                stop.address,
                phone_str,
                leg_dist,
                leg_dur,
                "[   ]",
            ])

        return output.getvalue()
