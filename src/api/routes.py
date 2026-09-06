# src/api/routes.py
# REST API route handlers for store search, directions, geocoding, and location management.
# Connects to: src/models/, src/services/google_maps.py, src/services/store_repository.py
# Created: 2026-09-06

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from src.config import settings
from src.models.directions import DirectionsResult, TravelMode
from src.models.geo import Coordinates, GeocodeResult
from src.models.store import Store, StoreCreate, StoreSummary
from src.models.trip import TripPlanRequest, TripPlanResponse
from src.services.google_maps import GoogleMapsService
from src.services.store_repository import StoreRepository
from src.services.trip_exporter import TripExporter
from src.services.trip_planner import TripPlannerService

router = APIRouter(prefix="/api", tags=["Store Locator"])

# Dependency injection helpers
_repo: Optional[StoreRepository] = None
_maps: Optional[GoogleMapsService] = None


def get_repository() -> StoreRepository:
    """Provide singleton instance of StoreRepository."""
    global _repo
    if _repo is None:
        _repo = StoreRepository()
    return _repo


def get_maps_service() -> GoogleMapsService:
    """Provide singleton instance of GoogleMapsService."""
    global _maps
    if _maps is None:
        _maps = GoogleMapsService()
    return _maps


def get_trip_planner(
    repo: StoreRepository = Depends(get_repository),
    maps: GoogleMapsService = Depends(get_maps_service),
) -> TripPlannerService:
    """Provide TripPlannerService configured with current repository and maps service."""
    return TripPlannerService(store_repo=repo, maps_service=maps)


class StoreSearchResponse(BaseModel):
    """Response payload for proximity store searches."""

    search_center: Coordinates
    search_address: str
    radius_km: float
    total_found: int
    stores: list[StoreSummary]


class SystemHealthResponse(BaseModel):
    """System status and Google Maps provider telemetry."""

    status: str
    version: str
    environment: str
    total_stores: int
    maps_provider: str
    live_maps_enabled: bool


@router.get("/health", response_model=SystemHealthResponse)
async def health_check(repo: StoreRepository = Depends(get_repository)) -> SystemHealthResponse:
    """Health check verifying database connection and Maps API provider status."""
    total = len(repo.list_all(limit=1000))
    return SystemHealthResponse(
        status="healthy",
        version=settings.app_version,
        environment=settings.app_env,
        total_stores=total,
        maps_provider="Google Maps Live Platform" if settings.is_live_google_maps_enabled else "Offline Mock Maps Engine",
        live_maps_enabled=settings.is_live_google_maps_enabled,
    )


@router.get("/config")
async def get_public_config() -> dict:
    """Return public frontend configuration including default coordinates and provider status."""
    return {
        "appName": settings.app_name,
        "defaultLat": settings.default_latitude,
        "defaultLng": settings.default_longitude,
        "defaultRadiusKm": settings.default_search_radius_km,
        "maxRadiusKm": settings.max_search_radius_km,
        "hasLiveApiKey": settings.is_live_google_maps_enabled,
        "googleMapsApiKey": settings.google_maps_api_key if settings.is_live_google_maps_enabled else None,
    }


@router.get("/geocode", response_model=GeocodeResult)
async def geocode_endpoint(
    address: Optional[str] = Query(None, description="Street address, city, or postal code"),
    lat: Optional[float] = Query(None, ge=-90.0, le=90.0, description="Latitude for reverse geocoding"),
    lng: Optional[float] = Query(None, ge=-180.0, le=180.0, description="Longitude for reverse geocoding"),
    maps: GoogleMapsService = Depends(get_maps_service),
) -> GeocodeResult:
    """Resolve an address query to coordinates or reverse geocode latitude/longitude coordinates."""
    if address:
        result = await maps.geocode(address)
        if not result:
            raise HTTPException(status_code=404, detail=f"No geographic coordinates found for address '{address}'")
        return result
    elif lat is not None and lng is not None:
        result = await maps.reverse_geocode(lat, lng)
        if not result:
            raise HTTPException(status_code=404, detail=f"No address found for coordinates {lat}, {lng}")
        return result
    else:
        raise HTTPException(status_code=400, detail="Must provide either 'address' query or both 'lat' and 'lng' coordinates")


@router.get("/stores", response_model=StoreSearchResponse)
@router.get("/stores/search", response_model=StoreSearchResponse)
async def search_stores(
    lat: Optional[float] = Query(None, ge=-90.0, le=90.0, description="Origin latitude in degrees"),
    lng: Optional[float] = Query(None, ge=-180.0, le=180.0, description="Origin longitude in degrees"),
    address: Optional[str] = Query(None, description="Search address, city, or zip code"),
    radius_km: float = Query(25.0, gt=0.0, le=500.0, description="Search radius in kilometers"),
    open_now: bool = Query(False, description="Filter only stores that are currently open"),
    min_rating: Optional[float] = Query(None, ge=0.0, le=5.0, description="Minimum customer rating (0-5)"),
    rating_45: Optional[bool] = Query(None, description="Filter stores with rating 4.5+"),
    drive_thru: Optional[bool] = Query(None, description="Filter stores with drive-thru"),
    curbside_pickup: Optional[bool] = Query(None, description="Filter stores with curbside pickup"),
    ev_charging: Optional[bool] = Query(None, description="Filter stores with EV charging"),
    wheelchair_accessible: Optional[bool] = Query(None, description="Filter stores with wheelchair accessibility"),
    wifi: Optional[bool] = Query(None, description="Filter stores with WiFi"),
    amenity: Optional[str] = Query(None, description="Filter by amenity (drive_thru, curbside_pickup, ev_charging, wifi, wheelchair_accessible)"),
    sort_by: str = Query("distance", pattern="^(distance|rating|name)$", description="Sort order"),
    limit: int = Query(50, ge=1, le=100, description="Maximum stores to return"),
    repo: StoreRepository = Depends(get_repository),
    maps: GoogleMapsService = Depends(get_maps_service),
) -> StoreSearchResponse:
    """Search for retail store locations near a coordinate point or resolved address.

    Calculates great-circle Haversine distances, applies operating hours evaluation,
    and returns rich store summaries.
    """
    origin_coords: Optional[Coordinates] = None
    resolved_address: str = ""

    if lat is not None and lng is not None:
        origin_coords = Coordinates(latitude=lat, longitude=lng)
        rev = await maps.reverse_geocode(lat, lng)
        resolved_address = rev.formatted_address if rev else f"{lat:.4f}, {lng:.4f}"
    elif address and address.strip():
        geo = await maps.geocode(address.strip())
        if not geo:
            raise HTTPException(status_code=404, detail=f"Address '{address}' could not be resolved by geocoding service")
        origin_coords = geo.coordinates
        resolved_address = geo.formatted_address
    else:
        # Fallback to default configured center (San Francisco)
        origin_coords = Coordinates(latitude=settings.default_latitude, longitude=settings.default_longitude)
        resolved_address = "San Francisco, CA, USA"

    effective_min_rating = min_rating
    if rating_45 and effective_min_rating is None:
        effective_min_rating = 4.5

    amenities_filter: dict[str, bool] = {}
    if drive_thru is not None and drive_thru:
        amenities_filter["drive_thru"] = True
    if curbside_pickup is not None and curbside_pickup:
        amenities_filter["curbside_pickup"] = True
    if ev_charging is not None and ev_charging:
        amenities_filter["ev_charging"] = True
    if wheelchair_accessible is not None and wheelchair_accessible:
        amenities_filter["wheelchair_accessible"] = True
    if wifi is not None and wifi:
        amenities_filter["wifi"] = True

    results = repo.search_nearby(
        latitude=origin_coords.latitude,
        longitude=origin_coords.longitude,
        radius_km=radius_km,
        open_now=open_now,
        min_rating=effective_min_rating,
        amenity=amenity,
        amenities_filter=amenities_filter if amenities_filter else None,
        sort_by=sort_by,
        limit=limit,
    )

    return StoreSearchResponse(
        search_center=origin_coords,
        search_address=resolved_address,
        radius_km=radius_km,
        total_found=len(results),
        stores=results,
    )


@router.get("/stores/{store_id}", response_model=Store)
async def get_store_details(
    store_id: int, repo: StoreRepository = Depends(get_repository)
) -> Store:
    """Fetch complete profile for a store including weekly hours, amenities, and customer reviews."""
    store = repo.get_by_id(store_id)
    if not store:
        raise HTTPException(status_code=404, detail=f"Store with ID {store_id} not found")
    return store


@router.post("/stores", response_model=Store, status_code=status.HTTP_201_CREATED)
async def create_store(
    store_data: StoreCreate,
    repo: StoreRepository = Depends(get_repository),
    maps: GoogleMapsService = Depends(get_maps_service),
) -> Store:
    """Register a new store branch. Geocodes street address if coordinates are not provided."""
    created = repo.add_store(store_data)
    return created


@router.get("/directions", response_model=DirectionsResult)
async def get_directions(
    origin_lat: Optional[float] = Query(None, ge=-90.0, le=90.0),
    origin_lng: Optional[float] = Query(None, ge=-180.0, le=180.0),
    origin_address: Optional[str] = Query(None),
    destination_store_id: Optional[int] = Query(None),
    dest_lat: Optional[float] = Query(None, ge=-90.0, le=90.0),
    dest_lng: Optional[float] = Query(None, ge=-180.0, le=180.0),
    mode: TravelMode = Query(TravelMode.DRIVING),
    repo: StoreRepository = Depends(get_repository),
    maps: GoogleMapsService = Depends(get_maps_service),
) -> DirectionsResult:
    """Calculate turn-by-turn directions, duration, distance, and encoded polyline from origin to destination."""
    # Resolve origin
    if origin_lat is not None and origin_lng is not None:
        origin = Coordinates(latitude=origin_lat, longitude=origin_lng)
        origin_name = origin_address or f"{origin_lat:.4f}, {origin_lng:.4f}"
    elif origin_address:
        geo = await maps.geocode(origin_address)
        if not geo:
            raise HTTPException(status_code=404, detail=f"Could not resolve origin address '{origin_address}'")
        origin = geo.coordinates
        origin_name = geo.formatted_address
    else:
        raise HTTPException(status_code=400, detail="Must provide origin coordinates (origin_lat, origin_lng) or origin_address")

    # Resolve destination
    if destination_store_id is not None:
        target_store = repo.get_by_id(destination_store_id)
        if not target_store:
            raise HTTPException(status_code=404, detail=f"Target store ID {destination_store_id} not found")
        destination = target_store.coordinates
        dest_name = f"{target_store.name}, {target_store.street}"
    elif dest_lat is not None and dest_lng is not None:
        destination = Coordinates(latitude=dest_lat, longitude=dest_lng)
        dest_name = f"{dest_lat:.4f}, {dest_lng:.4f}"
    else:
        raise HTTPException(status_code=400, detail="Must provide either destination_store_id or destination coordinates (dest_lat, dest_lng)")

    return await maps.directions(
        origin=origin,
        destination=destination,
        mode=mode,
        origin_name=origin_name,
        destination_name=dest_name,
    )


@router.post("/trip/plan", response_model=TripPlanResponse)
async def plan_multi_stop_trip(
    request: TripPlanRequest,
    planner: TripPlannerService = Depends(get_trip_planner),
) -> TripPlanResponse:
    """Plan an optimized multi-stop trip visiting 2 to 12 stores with TSP waypoint sequencing."""
    try:
        return await planner.plan_trip(request)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.get("/trip/preview", response_model=TripPlanResponse)
async def preview_multi_stop_trip(
    origin: str = Query(..., description="Origin address, city, or coordinates"),
    stores: str = Query(..., description="Comma-separated store IDs, e.g. '1,3,5'"),
    round_trip: bool = Query(True, description="Whether to return to origin"),
    optimize: bool = Query(True, description="Whether to apply TSP optimization"),
    mode: TravelMode = Query(TravelMode.DRIVING, description="Travel mode"),
    planner: TripPlannerService = Depends(get_trip_planner),
) -> TripPlanResponse:
    """Quick GET endpoint to preview an optimized multi-stop trip."""
    try:
        store_ids = [int(s.strip()) for s in stores.split(",") if s.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Store IDs must be a comma-separated list of integers.")

    if len(store_ids) < 2:
        raise HTTPException(status_code=400, detail="At least 2 store IDs are required for multi-stop planning.")

    req = TripPlanRequest(
        origin=origin,
        store_ids=store_ids,
        round_trip=round_trip,
        optimize=optimize,
        travel_mode=mode,
    )
    try:
        return await planner.plan_trip(req)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.post("/trip/export/gpx")
async def export_trip_gpx(
    plan: TripPlanResponse,
) -> Response:
    """Export a calculated TripPlanResponse as GPS Exchange Format (GPX 1.1) XML file."""
    gpx_xml = TripExporter.generate_gpx(plan)
    return Response(
        content=gpx_xml,
        media_type="application/gpx+xml",
        headers={"Content-Disposition": 'attachment; filename="route.gpx"'},
    )


@router.post("/trip/export/csv")
async def export_trip_csv(
    plan: TripPlanResponse,
) -> Response:
    """Export a calculated TripPlanResponse as a CSV driver delivery manifest."""
    csv_text = TripExporter.generate_csv(plan)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="driver_manifest.csv"'},
    )


@router.post("/trip/export/url")
async def export_trip_url(
    plan: TripPlanResponse,
) -> dict:
    """Generate universal cross-platform Google Maps mobile navigation URL."""
    url = TripExporter.generate_google_maps_url(plan)
    return {"google_maps_url": url}

