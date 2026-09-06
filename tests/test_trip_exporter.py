# tests/test_trip_exporter.py
# Unit and integration tests for route export: Google Maps deep links, GPX 1.1 XML, and CSV driver manifests.
# Connects to: src/services/trip_exporter.py, src/api/routes.py, src/models/trip.py
# Created: 2026-09-06

import xml.etree.ElementTree as ET
import httpx
import pytest
from src.models.directions import TravelMode
from src.models.geo import Coordinates
from src.models.trip import TripLeg, TripPlanResponse, WaypointNode
from src.services.trip_exporter import TripExporter


def make_dummy_plan() -> TripPlanResponse:
    """Construct a mock 3-stop trip plan for testing export serializations."""
    stop_0 = WaypointNode(
        sequence_index=0,
        name="Starting Point",
        address="100 Market St, San Francisco, CA",
        coordinates=Coordinates(latitude=37.7925, longitude=-122.3980),
        is_origin=True,
    )
    stop_1 = WaypointNode(
        sequence_index=1,
        name="Apex Retail - Union Square",
        address="300 Post St, San Francisco, CA",
        coordinates=Coordinates(latitude=37.7878, longitude=-122.4061),
        store_id=1,
    )
    stop_2 = WaypointNode(
        sequence_index=2,
        name="Starting Point",
        address="100 Market St, San Francisco, CA",
        coordinates=Coordinates(latitude=37.7925, longitude=-122.3980),
        is_destination=True,
    )

    leg_0 = TripLeg(
        leg_index=0,
        start_node=stop_0,
        end_node=stop_1,
        distance_km=1.5,
        distance_miles=0.9,
        distance_text="0.9 mi",
        duration_minutes=6.0,
        duration_text="6 mins",
    )
    leg_1 = TripLeg(
        leg_index=1,
        start_node=stop_1,
        end_node=stop_2,
        distance_km=1.5,
        distance_miles=0.9,
        distance_text="0.9 mi",
        duration_minutes=6.0,
        duration_text="6 mins",
    )

    return TripPlanResponse(
        origin_label="100 Market St, San Francisco, CA",
        destination_label="100 Market St, San Francisco, CA",
        round_trip=True,
        travel_mode=TravelMode.DRIVING,
        optimized=True,
        optimized_store_ids=[1],
        stops=[stop_0, stop_1, stop_2],
        legs=[leg_0, leg_1],
        total_distance_km=3.0,
        total_distance_miles=1.8,
        total_distance_text="1.8 mi",
        total_duration_minutes=12.0,
        total_duration_text="12 mins",
        overview_polyline="dummy_polyline_string",
    )


def test_generate_google_maps_url():
    """Google Maps URL must contain origin, destination, intermediate waypoints, and travelmode."""
    plan = make_dummy_plan()
    url = TripExporter.generate_google_maps_url(plan)

    assert url.startswith("https://www.google.com/maps/dir/?")
    assert "api=1" in url
    assert "origin=37.792500%2C-122.398000" in url
    assert "destination=37.792500%2C-122.398000" in url
    assert "waypoints=37.787800%2C-122.406100" in url
    assert "travelmode=driving" in url


def test_generate_google_maps_url_empty():
    """Empty or short plans fallback safely to base Google Maps URL."""
    plan = make_dummy_plan()
    plan.stops = []
    assert TripExporter.generate_google_maps_url(plan) == "https://www.google.com/maps"


def test_generate_gpx():
    """GPX export must produce valid GPX 1.1 XML containing waypoints and route tags."""
    plan = make_dummy_plan()
    gpx_str = TripExporter.generate_gpx(plan)

    assert "<?xml version=" in gpx_str
    assert '<gpx version="1.1"' in gpx_str

    # Validate XML parsing
    root = ET.fromstring(gpx_str)
    assert root.tag.endswith("gpx")

    # Check waypoints exist
    wpts = [elem for elem in root.iter() if elem.tag.endswith("wpt")]
    assert len(wpts) == 3

    # Check route points exist
    rtepts = [elem for elem in root.iter() if elem.tag.endswith("rtept")]
    assert len(rtepts) == 3


def test_generate_csv():
    """CSV export must include driver headers and stop details."""
    plan = make_dummy_plan()
    csv_str = TripExporter.generate_csv(plan)

    assert "# Total Distance,1.8 mi" in csv_str
    assert "Stop #,Stop Type,Store / Location Name" in csv_str
    assert "Apex Retail - Union Square" in csv_str
    assert "100 Market St, San Francisco, CA" in csv_str


@pytest.mark.asyncio
async def test_api_export_gpx(client: httpx.AsyncClient):
    """POST /api/trip/export/gpx returns downloadable GPX XML."""
    plan = make_dummy_plan()
    res = await client.post("/api/trip/export/gpx", json=plan.model_dump())
    assert res.status_code == 200
    assert "application/gpx+xml" in res.headers["content-type"]
    assert 'filename="route.gpx"' in res.headers["content-disposition"]
    assert '<gpx version="1.1"' in res.text


@pytest.mark.asyncio
async def test_api_export_csv(client: httpx.AsyncClient):
    """POST /api/trip/export/csv returns downloadable CSV manifest."""
    plan = make_dummy_plan()
    res = await client.post("/api/trip/export/csv", json=plan.model_dump())
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert 'filename="driver_manifest.csv"' in res.headers["content-disposition"]
    assert "Stop #" in res.text


@pytest.mark.asyncio
async def test_api_export_url(client: httpx.AsyncClient):
    """POST /api/trip/export/url returns JSON with google_maps_url."""
    plan = make_dummy_plan()
    res = await client.post("/api/trip/export/url", json=plan.model_dump())
    assert res.status_code == 200
    data = res.json()
    assert "google_maps_url" in data
    assert "https://www.google.com/maps/dir/" in data["google_maps_url"]
