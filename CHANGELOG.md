# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2026-09-06

### Added
- **Multi-Platform Route Export Engine** (`src/services/trip_exporter.py`):
  - Added `TripExporter` service generating official Google Maps Universal Cross-Platform Navigation URLs (`https://www.google.com/maps/dir/?api=1&...`) with origin, destination, intermediate waypoints, and travel mode.
  - Implemented GPS Exchange Format (GPX 1.1) XML serialization with metadata, `<wpt>` waypoint nodes, and `<rte>` route elements compatible with Garmin units, GPS watches, OsmAnd, and car infotainment systems.
  - Implemented tabular CSV driver delivery manifest generation containing sequence numbers, stop types, store profiles, phone contacts, leg distances, drive durations, and physical signature blanks.
- **Route Export REST Endpoints** (`src/api/routes.py`):
  - `POST /api/trip/export/gpx`: Returns downloadable `route.gpx` with `application/gpx+xml` media type and attachment headers.
  - `POST /api/trip/export/csv`: Returns downloadable `driver_manifest.csv` with `text/csv` media type and attachment headers.
  - `POST /api/trip/export/url`: Returns serialized JSON with the Google Maps navigation deep link.
- **CLI Export Capabilities** (`src/cli/main.py`):
  - Extended `store-locator trip` command with `--export-gpx <path>`, `--export-csv <path>`, and `--show-url` flags for automated route serialization directly to disk.
- **Frontend Export & Print Actions** (`src/static/index.html`, `src/static/styles.css`, `src/static/app.js`):
  - Added Export Toolbar inside the Multi-Stop Itinerary Modal featuring:
    - `📱 Open in Google Maps`: 1-click mobile handoff launching native Google Maps app with turn-by-turn navigation.
    - `📷 QR Handoff`: Dynamic popover generating a camera-scannable QR code for instant mobile transfer.
    - `💾 Download GPX`: 1-click download of `.gpx` route files for standalone GPS devices.
    - `📄 Driver Manifest (CSV)`: 1-click export of driver delivery manifests.
    - `🖨️ Print Route Slip`: Dedicated physical print stylesheet (`@media print`) rendering clean delivery manifests with driver check-off blanks.
- **Filter Conjunction & Rating/Amenity Enhancements** (`src/api/routes.py`, `src/services/store_repository.py`, `src/static/app.js`):
  - Added multi-amenity conjunction (AND) filtering across `drive_thru`, `curbside_pickup`, `ev_charging`, `wheelchair_accessible`, and `wifi`.
  - Added automatic mapping of `rating_45` to `min_rating=4.5`.
  - Added interactive "Reset All Filters" recovery action when active filters yield 0 results.
- **Automated Tests** (`tests/test_trip_exporter.py`, `tests/test_cli.py`, `tests/test_api.py`):
  - Added 12 new automated test cases verifying GPX XML parsing, CSV formatting, Google Maps deep-link schemas, export REST endpoints, and CLI export flags, bringing total passing test suite to 68 tests.

## [1.1.0] - 2026-09-06

### Added
- **Multi-Stop Trip Planning & TSP Optimization** (`src/models/trip.py`, `src/utils/optimizer.py`, `src/services/trip_planner.py`):
  - Added Traveling Salesperson Problem (TSP) spatial route optimizer supporting exact brute-force permutation solver for sets of up to 8 waypoints and greedy Nearest-Neighbor with 2-opt local search heuristic for larger store sets.
  - Implemented symmetric pairwise Haversine distance matrix generator in kilometers and miles.
  - Quantified route efficiency savings calculation reporting kilometers saved, miles saved, percentage distance reduction, and estimated driving minutes saved over naive visiting sequences.
  - Added `TripPlannerService` coordinating store retrieval, geocoding origin addresses, TSP sequence resolution, leg-by-leg navigation calculation, and composite polyline compilation.
- **Trip Planning REST API Endpoints** (`src/api/routes.py`):
  - `POST /api/trip/plan`: Accepts `TripPlanRequest` and returns `TripPlanResponse` with ordered stops, leg steps, polylines, and savings metrics.
  - `GET /api/trip/preview`: Quick GET endpoint for multi-stop route previews.
- **CLI Trip Planning Command** (`src/cli/main.py`):
  - Added `store-locator trip` command supporting `--origin`, `-s/--store` (multiple), `--round-trip/--one-way`, `--optimize/--no-optimize`, and `--mode`.
  - Rich console output with formatted itinerary overview panel, route efficiency savings callout, chronological stop schedule table, and leg-by-leg segment details.
- **Frontend Multi-Stop UI Enhancements** (`src/static/index.html`, `src/static/styles.css`, `src/static/app.js`):
  - Added "+ Trip" / "✓ In Trip" toggle buttons to store cards in search results.
  - Implemented floating bottom Trip Planner Bar showing selected store count, dismissible store pills, round-trip/optimize toggles, and "Calculate Route" action.
  - Built full Multi-Stop Itinerary Modal with savings banner, 4-stat metrics grid, chronological timeline, and expandable leg segments.
  - Enhanced SVG Geospatial Canvas Map to draw composite multi-stop route polylines and numbered waypoint pins for trip stops.
- **Automated Tests**:
  - Added 16 new automated tests in `tests/test_optimizer.py`, `tests/test_trip_planner.py`, `tests/test_trip_api.py`, and `tests/test_cli.py` bringing total test suite to 56 tests passing 100%.

## [1.0.0] - 2026-09-06

### Added
- **Core Domain & Data Models** (`src/models/`):
  - `Store`, `WeeklyHours`, `DayHours`, `StoreReview`, and `StoreAmenities` models with strict Pydantic v2 schemas.
  - `Coordinates`, `BoundingBox`, `GeocodeResult`, and `DistanceResult` models for spatial data representation.
  - `DirectionsRequest`, `DirectionsResult`, `RouteStep`, and `TravelMode` (driving, walking, bicycling, transit) models.
- **Geospatial & Hours Algorithms** (`src/utils/`):
  - Great-Circle Haversine distance formula calculating distances in kilometers and miles.
  - Latitude/Longitude bounding-box pre-filtering calculator for indexed spatial queries.
  - Compass bearing calculation (0° - 360°).
  - Business hours evaluation engine determining real-time "Open Now" status, "Closing Soon" alerts (<= 45 mins), and 12-hour formatted operating hours.
  - Google Maps Encoded Polyline encoder and decoder algorithm for route geometry compression.
- **Google Maps Integration & Offline Simulation** (`src/services/`):
  - `GoogleMapsService`: HTTP client for Google Maps Platform APIs (Geocoding, Directions, Places) with exponential backoff on 429/5xx status codes and parameter redaction.
  - `MockGoogleMapsService`: High-fidelity offline simulation engine providing deterministic geocoding for major cities and zip codes, and realistic routing with polyline interpolation when no live API key is configured.
- **SQLite Spatial Persistence** (`src/services/store_repository.py`):
  - Thread-safe repository storing store branches, weekly schedules, amenities, and customer ratings.
  - Automatic database seeding with 16 realistic flagship store locations across San Francisco, New York, Seattle, Chicago, Austin, Los Angeles, and Denver.
  - Spatial search combining SQL bounding-box indexing, exact Haversine distance calculation, operating hours evaluation, and amenity filtering.
- **FastAPI REST API Engine** (`src/api/`):
  - `GET /api/stores`: Proximity store search with filters for radius, open now, minimum rating, and amenities.
  - `GET /api/stores/{id}`: Detailed store profile with weekly hours and verified reviews.
  - `POST /api/stores`: Create new store branch with automatic address geocoding.
  - `GET /api/directions`: Turn-by-turn navigation route calculation with step-by-step instructions.
  - `GET /api/geocode`: Address geocoding and reverse geocoding endpoints.
  - `GET /api/health` & `GET /api/config`: System telemetry and frontend runtime configuration.
- **Rich Command-Line Suite** (`src/cli/`):
  - Installable CLI entry point `store-locator` with `--version`, `search`, `directions`, `get`, `list`, and `serve` commands.
- **Interactive Responsive Map Frontend** (`src/static/`):
  - Single-page application served directly by FastAPI.
  - Responsive layout with search bar, HTML5 geolocation ("Locate Me"), radius slider, filter chips, and store cards.
  - Dual-engine map renderer supporting Google Maps JavaScript API and responsive SVG geospatial canvas fallback with custom open/closed markers, user radar pin, and navigation route polyline.
  - Interactive turn-by-turn directions drawer and detailed store modal.
- **Test Suite & CI Workflow**:
  - 40 automated unit and integration tests across distance, hours, polyline, mock maps, repository, REST API, and CLI suites.
  - GitHub Actions CI matrix testing across Python 3.10, 3.11, and 3.12.
