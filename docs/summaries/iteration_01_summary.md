# Engineering Summary — Iteration 01: Core Google Maps Platform Integration, Haversine Proximity Search, Real-Time Operating Hours, Turn-by-Turn Navigation & Interactive Map UI

**Build Reference**: Build 140  
**Version**: `v1.0.0`  
**Status**: Completed & Verified  

---

## 1. Overview & Objective

The primary objective of Iteration 1 was to engineer an advanced, production-grade geospatial retail store locator and navigation engine (`google-maps-store-locator`). The platform allows users and client applications to find the nearest store locations given an address or GPS coordinate point, computes exact Great-Circle Haversine distances, applies real-time operating hours evaluation to display "Open Now" or "Closing Soon" statuses, and provides complete turn-by-turn navigation routing with encoded polylines across Driving, Walking, Bicycling, and Transit modes.

The architecture is built for production resilience: it communicates with official Google Maps Platform APIs (Geocoding, Directions, Places) when an API key is configured, and seamlessly falls back to a high-fidelity offline simulation engine when running offline or in testing, ensuring zero external billing dependencies for local development and continuous integration pipelines.

---

## 2. Key Architecture & Modules Introduced

### `src/models/`
- **`geo.py`**: Pydantic v2 schemas for geographic points (`Coordinates`), spatial rectangles (`BoundingBox`), geocoding responses (`GeocodeResult`), and distance metrics (`DistanceResult`).
- **`store.py`**: Comprehensive domain model for retail branches (`Store`), 7-day weekly operating schedules (`WeeklyHours`, `DayHours`), customer review collections (`StoreReview`), amenity toggles (`StoreAmenities`), and enriched search summaries (`StoreSummary`).
- **`directions.py`**: Navigation routing structures including transportation modes (`TravelMode`), turn-by-turn instructions (`RouteStep`), directions requests (`DirectionsRequest`), and complete route responses (`DirectionsResult`).

### `src/utils/`
- **`distance.py`**: High-precision Great-Circle Haversine distance formula calculating distances in kilometers and miles. Includes latitude/longitude bounding-box pre-filtering calculator for indexed SQL queries, and compass bearing calculations (0° - 360°).
- **`hours.py`**: Business operating hours engine evaluating whether a store is open right now, calculating closing-soon notices (<= 45 minutes remaining), handling overnight hours, and formatting 12-hour AM/PM representations.
- **`polyline.py`**: Full implementation of the Google Maps Encoded Polyline algorithm supporting lossless route geometry encoding and decoding.

### `src/services/`
- **`google_maps.py`**: Asynchronous HTTP client communicating with Google Maps Platform Geocoding and Directions APIs using HTTPX. Features exponential backoff on 429/5xx status codes, request parameter masking, and seamless fallback to mock services.
- **`mock_maps.py`**: High-fidelity offline simulation engine providing deterministic geocoding for major metropolitan cities and postal codes, and turn-by-turn route calculations with interpolated polyline paths.
- **`store_repository.py`**: Thread-safe SQLite repository managing store persistence. Automatically seeds 16 realistic flagship store locations across San Francisco, New York, Seattle, Chicago, Austin, Los Angeles, and Denver. Implements spatial search combining bounding-box SQL indexing with exact Haversine distance filtering.

### `src/api/`
- **`routes.py`**: REST API endpoints for proximity store searching (`GET /api/stores`), store profile inspection (`GET /api/stores/{id}`), store creation (`POST /api/stores`), turn-by-turn routing (`GET /api/directions`), geocoding (`GET /api/geocode`), and telemetry (`GET /api/health`, `GET /api/config`).
- **`app.py`**: FastAPI application factory with permissive CORS middleware, static asset mounting, and structured logging.

### `src/cli/`
- **`main.py`**: Installable Click and Rich command-line suite providing commands: `--version`, `search`, `directions`, `get`, `list`, and `serve`. Fully optimized with ASCII-safe formatting for Windows `cp1252` and UNIX terminals.

### `src/static/`
- **`index.html` & `styles.css`**: Responsive single-page application with split-screen sidebar and map layout, search input, HTML5 geolocation ("Locate Me"), radius dropdown, amenity filter chips, and store details modal.
- **`app.js`**: Frontend client controller supporting dual-engine map rendering (Google Maps JavaScript API + interactive SVG geospatial vector canvas fallback), user radar pin, and turn-by-turn directions drawer.

---

## 3. Complete File Breakdown & Architecture Connections

| File Path | Description | Connection |
| :--- | :--- | :--- |
| `AGENTS.md` | Non-negotiable engineering standards and conventions. | Root governance |
| `LICENSE` | Standard MIT License for open-source distribution. | Legal / Compliance |
| `.env.example` | Runtime environment variable template (no hardcoded secrets). | Environment config |
| `pyproject.toml` | Standard Python packaging manifest with installable CLI entry point. | Packaging |
| `requirements.txt` | Explicit pinned application dependencies. | Dependencies |
| `.github/workflows/ci.yml` | Multi-version Python CI matrix workflow (3.10, 3.11, 3.12). | CI / CD |
| `src/__init__.py` | Root package initializer. | Package root |
| `src/config.py` | Typed application settings via Pydantic Settings. | Config provider |
| `src/models/geo.py` | Geographic point, bounding box, and geocoding models. | Domain model |
| `src/models/store.py` | Store entity, operating hours, amenities, and review models. | Domain model |
| `src/models/directions.py` | Turn-by-turn routing, step, and polyline models. | Domain model |
| `src/models/__init__.py` | Domain model exports. | Model exports |
| `src/utils/distance.py` | Haversine distance, bounding box, and bearing math. | Geospatial math |
| `src/utils/hours.py` | Real-time operating hours and "Open Now" evaluator. | Time evaluation |
| `src/utils/polyline.py` | Google Maps encoded polyline encoder and decoder. | Polyline algorithms |
| `src/utils/__init__.py` | Utility function exports. | Utility exports |
| `src/services/mock_maps.py` | Offline mock Google Maps simulation engine. | Mock service |
| `src/services/google_maps.py` | Production Google Maps Platform HTTP client with retries. | Live Maps API |
| `src/services/store_repository.py` | SQLite repository, spatial queries, and seed data. | Persistence |
| `src/services/__init__.py` | Service layer exports. | Service exports |
| `src/api/routes.py` | REST API routes for stores, directions, and geocoding. | API routing |
| `src/api/app.py` | FastAPI application factory and static file serving. | Web server |
| `src/api/__init__.py` | API module exports. | API exports |
| `src/cli/main.py` | Rich CLI command suite (`store-locator`). | CLI entry point |
| `src/cli/__init__.py` | CLI package initialization. | CLI package |
| `src/static/styles.css` | Modern responsive styling system for map and sidebar. | Frontend styles |
| `src/static/index.html` | Single-page application markup for store locator UI. | Frontend markup |
| `src/static/app.js` | Client-side map controller and reactive state manager. | Frontend logic |
| `tests/conftest.py` | Isolated SQLite database and HTTP client test fixtures. | Test setup |
| `tests/test_distance.py` | Unit tests for Haversine distance, bounding box, bearings. | Test suite |
| `tests/test_hours.py` | Unit tests for operating hours and "Open Now" calculations. | Test suite |
| `tests/test_polyline.py` | Unit tests for polyline encoding and decoding algorithms. | Test suite |
| `tests/test_mock_maps.py` | Unit tests for offline mock Google Maps service. | Test suite |
| `tests/test_store_repository.py` | Integration tests for SQLite repository and spatial queries. | Test suite |
| `tests/test_api.py` | Integration tests for all FastAPI REST endpoints. | Test suite |
| `tests/test_cli.py` | CLI execution tests for version, search, directions, list. | Test suite |
| `README.md` | Comprehensive product documentation and API guide. | Documentation |
| `CHANGELOG.md` | Technical release notes adhering to Keep a Changelog. | Release notes |
| `ITERATIONS.md` | Public chronological iteration log and commit references. | Public audit |
| `BUILD_NOTES.md` | Plain-English conversational development log (git-ignored). | Developer log |

---

## 4. Exact Manual Test Steps in Another Terminal Window

Open a second terminal window and execute the following commands to verify the build:

```bash
# Navigate to project directory
cd google-maps-store-locator-build140  # or: cd Build_140

# Activate virtual environment
venv\Scripts\activate  # On Windows
# source venv/bin/activate  # On macOS/Linux

# 1. Verify CLI Version
store-locator --version
# Expected: store-locator, version 1.0.0

# 2. Search for stores nearest to San Francisco within 15 km
store-locator search --address "San Francisco" --radius 15 --limit 3
# Expected: Tabular list showing SoMa Tech Center, Mission District, and Union Square with distance, status, and amenities

# 3. Search with real-time "Open Now" filter and minimum rating
store-locator search --address "Market St, San Francisco" --open-now --min-rating 4.7 --limit 3
# Expected: Only stores currently open with ratings >= 4.7

# 4. Calculate turn-by-turn driving directions to Store #1
store-locator directions --from-loc "Market St" --to-store 1 --mode driving
# Expected: Route summary card, total distance/time, and 4 turn-by-turn navigation steps

# 5. Inspect store details and full weekly operating hours
store-locator get 1
# Expected: Detailed store profile, phone, weekly schedule table, amenities, and customer reviews

# 6. Run the complete automated test suite
pytest -v --tb=short
# Expected: 40 passed in < 1.0s (100% pass rate)

# 7. Launch the local web application
store-locator serve --port 8000
# Open http://localhost:8000 in your browser to interact with the responsive map UI, search locations, toggle filter chips, view directions, and inspect store profiles!
```

---

## 5. Candidate Next Iterations

### Option 1: Multi-Stop Trip Planner & Route Optimization (Traveling Salesperson)
- **Plain English**: Allows users to select multiple stores or delivery destinations and computes the most fuel-efficient route visiting all locations using Google Maps Distance Matrix and heuristic TSP optimization.
- **Benefit**: Essential for enterprise field logistics, mobile technicians, multi-store inventory auditing, and shoppers running errands across multiple retail branches.
- **Trade-off**: Increases route computation latency for large numbers of waypoints; requires Distance Matrix API quota or combinatorial approximation algorithms.
- **Interview Answer**: *"I added a multi-stop route optimization engine that computes pairwise distance matrices and applies a branch-and-bound traveling salesperson algorithm to order stops for minimum total drive time."*
- **Manual Test Steps**:
  1. Run `store-locator trip --stops 1,2,3 --optimize`.
  2. Verify that the output displays an ordered sequence of stores minimizing total drive mileage compared to the unoptimized input.

### Option 2: Live Traffic Layer & Isochrone Drive-Time Contours
- **Plain English**: Visualizes real-time traffic congestion on the map and computes isochrone polygons representing the geographic area reachable within a 10, 20, or 30-minute drive factoring in current traffic.
- **Benefit**: Provides users with realistic travel expectations during rush hour and helps businesses analyze retail store catchment trade areas.
- **Trade-off**: Requires Google Maps Roads / Traffic APIs or precomputed historical traffic speed profiles, increasing complexity.
- **Interview Answer**: *"I integrated drive-time isochrone generation by querying traffic-aware travel durations across radial bearings and rendering concave geographic catchment hulls."*
- **Manual Test Steps**:
  1. Open the web UI and toggle the "Drive Time" filter to 15 minutes.
  2. Verify that the map displays a shaded isochrone contour polygon with stores outside the drive-time boundary filtered out.

### Option 3: GeoJSON & CSV Batch Importer with Address Verification
- **Plain English**: Enables administrators to bulk upload thousands of retail store locations via CSV or GeoJSON files with automated asynchronous address geocoding, deduplication, and schema validation.
- **Benefit**: Solves the enterprise onboarding challenge of migrating nationwide retail franchise locations into the store locator platform without manual data entry.
- **Trade-off**: Requires bulk rate-limiting queues and error recovery mechanics to handle malformed addresses or API geocoding quota limits.
- **Interview Answer**: *"I engineered an asynchronous batch ingestion pipeline that parses CSV store directories, deduplicates records against existing spatial coordinates, and processes geocoding requests with rate-limiting chunking."*
- **Manual Test Steps**:
  1. Run `store-locator import stores_sample.csv`.
  2. Verify that all rows are validated, geocoded, and added to the SQLite database with progress bar accounting.

### Option 4: Store Inventory & Real-Time Stock Availability Checker
- **Plain English**: Connects store locations to an inventory SKU catalog, allowing customers to search for a specific product and see which nearby stores have it in stock before visiting.
- **Benefit**: Drives high-intent foot traffic to physical retail stores and eliminates the frustration of arriving at a store only to find the desired product out of stock.
- **Trade-off**: Introduces inventory ledger models and multi-table joins, increasing database complexity.
- **Interview Answer**: *"I added an inventory catalog layer that joins SKU availability with geospatial store searches, enabling customers to filter the map by product in-stock status within their radius."*
- **Manual Test Steps**:
  1. Search for a product SKU via `store-locator search --product-sku "TECH-401" --in-stock`.
  2. Verify that only stores with quantity > 0 for that product are returned.
