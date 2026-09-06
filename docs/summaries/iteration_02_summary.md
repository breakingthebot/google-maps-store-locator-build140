# Engineering Summary — Iteration 02: Multi-Stop Trip Planner & Route Optimization (TSP)

**Build Reference**: Build 140  
**Version**: `v1.1.0`  
**Status**: Completed & Verified  

---

## 1. Overview & Objective

The primary objective of Iteration 2 was to implement an intelligent, enterprise-grade **Multi-Stop Trip Planner with Route Optimization** solving the Traveling Salesperson Problem (TSP) for retail shoppers, regional facility inspectors, and multi-drop delivery drivers.

Visiting multiple store locations in arbitrary or alphabetical sequence often results in erratic crisscrossing across cities, unnecessary traffic delays, excessive mileage, and high fuel consumption. Iteration 2 introduces a spatial route optimizer that models the journey as a complete geometric graph, evaluates all candidate stop sequences, reorders the waypoints into the mathematically minimal path, and calculates quantified savings metrics (miles saved, kilometers saved, percentage distance reduction, and estimated driving minutes saved).

The feature is fully accessible through a new REST API endpoint (`POST /api/trip/plan`), an enhanced Rich terminal CLI command (`store-locator trip`), and interactive web UI controls including a floating Trip Planner bar, "+ Trip" / "✓ In Trip" store card toggles, a multi-stop itinerary drawer modal, and composite multi-leg polyline rendering on the interactive map canvas.

---

## 2. Key Architecture & Modules Introduced

### `src/models/trip.py` (New)
- **`WaypointNode`**: Data schema representing a node along a multi-stop itinerary (origin, store, or return point) with sequence indices, addresses, and coordinates.
- **`TripLeg`**: Models an individual segment of travel between two consecutive stops with distance, duration, turn-by-turn steps (`RouteStep`), and encoded polyline string.
- **`TripSavings`**: Captures quantified efficiency gains: `naive_distance_km`, `optimized_distance_km`, `distance_saved_km`, `distance_saved_miles`, `percentage_distance_saved`, and `estimated_minutes_saved`.
- **`TripPlanRequest`**: Payload schema accepting origin (address string or coordinates), `store_ids` (2 to 12 stores), `round_trip` toggle, `optimize` toggle, and `travel_mode`.
- **`TripPlanResponse`**: Complete itinerary response with sequenced stops, navigation legs, total cumulative stats, overview polyline, and savings metrics.

### `src/utils/optimizer.py` (New)
- **`compute_distance_matrix`**: Generates an $N \times N$ symmetric pairwise distance matrix using the Haversine great-circle formula.
- **`compute_tour_distance`**: Calculates the exact cumulative distance of any tour sequence, optionally adding the closing return leg back to node 0.
- **`solve_tsp_bruteforce`**: Mathematically exact permutation optimizer for sets of $N \le 9$ nodes ($8! = 40,320$ permutations), evaluating in under 20 milliseconds in pure Python.
- **`solve_tsp_2opt`**: Fast heuristic solver combining Nearest-Neighbor greedy tour initialization with iterative 2-opt edge-reversal search for larger node sets.
- **`optimize_route`**: High-level solver selecting between brute-force and 2-opt based on input set size and computing naive vs. optimized tour costs.

### `src/services/trip_planner.py` (New)
- **`TripPlannerService`**: Coordinates store retrieval from `StoreRepository`, origin resolution via geocoding, TSP sequence optimization, leg-by-leg navigation routing via `GoogleMapsService` / `MockGoogleMapsService`, and composite polyline compilation. Provides async-safe wrappers to handle both sync mock services and async HTTP clients.

### `src/api/routes.py` (Updated)
- **`POST /api/trip/plan`**: Accepts `TripPlanRequest` and returns `TripPlanResponse`. Validates store existence and minimum waypoint counts.
- **`GET /api/trip/preview`**: Quick GET query endpoint for multi-stop routing previews (`?origin=...&stores=1,2,4`).

### `src/cli/main.py` (Updated)
- **`store-locator trip`**: New terminal command with options `--origin`, `-s/--store` (multiple), `--round-trip/--one-way`, `--optimize/--no-optimize`, and `--mode`. Renders Rich terminal panels, route efficiency savings banners, chronological stop schedule tables, and leg-by-leg segment tables.

### `src/static/` (Updated)
- **`index.html`**: Added floating Trip Planner Bar (`#trip-bar`) with store counter badge, store pills, and route controls. Added Multi-Stop Itinerary Modal (`#trip-modal`) with savings callout banner, 4-stat metrics grid, chronological timeline, and leg accordions.
- **`styles.css`**: Styling for trip toggle buttons, floating bottom bar, dismissible store chips, emerald savings banner, stat cards, and timeline connectors.
- **`app.js`**: Frontend trip planner controller managing selection state, invoking `/api/trip/plan`, decoding composite polylines, and rendering waypoint pins (`A`, `1`, `2`, `3`, `★`) on the interactive SVG canvas map.

---

## 3. Complete File Breakdown & Architecture Connections

| File Path | Change Type | Description | Connected Modules |
| :--- | :---: | :--- | :--- |
| `src/models/trip.py` | Created | Pydantic schemas for waypoints, legs, trip requests, responses, and savings. | `src/models/directions.py`, `src/services/trip_planner.py` |
| `src/utils/optimizer.py` | Created | TSP route optimization, distance matrix calculation, brute-force & 2-opt solvers. | `src/utils/distance.py`, `src/services/trip_planner.py` |
| `src/services/trip_planner.py` | Created | Orchestrates store lookups, geocoding, TSP solving, and multi-leg route generation. | `src/services/store_repository.py`, `src/services/google_maps.py` |
| `src/utils/polyline.py` | Updated | Resilient polyline encoder supporting both `Coordinates` instances and coordinate tuples. | `src/services/trip_planner.py`, `src/services/mock_maps.py` |
| `src/api/routes.py` | Updated | Added `POST /api/trip/plan` and `GET /api/trip/preview` endpoints. | `src/services/trip_planner.py`, `src/models/trip.py` |
| `src/cli/main.py` | Updated | Added `store-locator trip` command with Rich formatted itinerary and savings tables. | `src/services/trip_planner.py`, `src/models/trip.py` |
| `src/static/index.html` | Updated | Injected floating Trip Planner bar, trip modal, savings banner, and timeline components. | `src/static/app.js`, `src/static/styles.css` |
| `src/static/styles.css` | Updated | Added styling for trip toggle pills, floating bottom bar, stat grid, and timeline connectors. | `src/static/index.html` |
| `src/static/app.js` | Updated | Controller for trip cart management, API submission, modal display, and map rendering. | `src/api/routes.py`, `src/static/index.html` |
| `tests/test_optimizer.py` | Created | Unit tests for distance matrix, brute-force optimality, 2-opt efficiency, and savings. | `src/utils/optimizer.py` |
| `tests/test_trip_planner.py` | Created | Integration tests for `TripPlannerService` round-trip, one-way, and validation errors. | `src/services/trip_planner.py` |
| `tests/test_trip_api.py` | Created | API tests for `/api/trip/plan` and `/api/trip/preview` endpoints. | `src/api/routes.py` |
| `tests/test_cli.py` | Updated | Added CLI test verifying `store-locator trip` terminal output. | `src/cli/main.py` |
| `README.md` | Updated | Added Trip Planner documentation, architecture diagram updates, and 56-test badge. | Documentation |
| `CHANGELOG.md` | Updated | Logged v1.1.0 changes per Keep a Changelog standard. | Documentation |
| `BUILD_NOTES.md` | Updated | Appended Iteration 2 plain-English log and technical rationale. | Documentation |

---

## 4. Manual Testing Verification Steps

To test Iteration 2 manually in another terminal window:

### Step 1: Run Automated Verification Suite
```bash
# In Build_140 root directory with venv active:
pytest
```
*Expected*: All 56 tests pass in ~1 second with 100% pass rate.

### Step 2: Test Multi-Stop Trip Planning via CLI
```bash
# Plan an optimized round-trip visiting stores 1, 2, and 4 starting from Market St
store-locator trip --origin "Market St" -s 1 -s 2 -s 4 --round-trip
```
*Expected Output*:
- Rich cyan panel: **Optimized Trip Overview** showing Origin, Destination, Total Distance (~7.1 mi), and Total Travel Time (~19 mins).
- Rich green panel: **Route Efficiency Savings** showing miles saved and percentage distance reduction.
- **Sequential Stop Schedule** table with numbered sequence roles (`Origin`, `Store #1`, `Store #4`, `Store #2`, `Return`).
- **Leg-by-Leg Route Segments** table showing distances and times for all 4 legs.

### Step 3: Test One-Way Walking Trip via CLI
```bash
store-locator trip --origin "San Francisco" -s 1 -s 2 --one-way --mode walking
```
*Expected Output*: Output displays walking itinerary ending at Store #2 without return leg.

### Step 4: Test REST API via cURL or PowerShell
```powershell
Invoke-RestMethod -Uri "http://localhost:8080/api/trip/preview?origin=Market%20St&stores=1,2,4&round_trip=true" -Method GET | ConvertTo-Json -Depth 3
```
*Expected*: JSON response returning `round_trip: true`, `optimized: true`, `stops` array, `legs` array, and `savings` object.

### Step 5: Test Web UI Multi-Stop Workflow in Browser
1. Ensure the server is running: `store-locator serve --port 8080`.
2. Open your browser to **http://localhost:8080**.
3. Search for **"San Francisco"**.
4. In the store card list, click **"+ Trip"** on Store 1.
   * Verify: The button turns blue with **"✓ In Trip"**, and a floating bar appears at the bottom: *"Multi-Stop Trip Planner (1)"*.
5. Click **"+ Trip"** on Store 2 and Store 4.
   * Verify: The badge counter updates to **"3"**, and 3 dismissible store pills appear.
6. Click **"🚀 Calculate Route"** in the floating bar.
   * Verify: The **Multi-Stop Itinerary Modal** opens.
   * Verify: Emerald savings banner shows mileage and time saved.
   * Verify: Summary cards display Total Distance, Travel Time, Stops count, and Mode.
   * Verify: Optimized Visit Schedule shows the stops in sequence (`A`, `1`, `2`, `3`, `★`).
   * Verify: The map draws the purple multi-stop polyline and numbered waypoint badges.

---

## 5. Candidate Next Iterations

### Option 1: Live Traffic Layer & Isochrone Drive-Time Contours
- **Plain English**: Shows realistic 5, 10, and 15-minute drive-time catchment areas on the map instead of simple straight-line radius circles, taking real street topography and road speeds into account.
- **Why**: Real customers do not travel as the crow flies. In retail site selection and marketing, 10-minute drive-time isochrones are the industry standard for determining store trade areas.
- **Trade-off**: Requires generating polygonal mesh contours or querying an isochrone matrix engine, which adds geometric polygon calculations.
- **Interview Answer**: *"Straight-line radius buffers misrepresent actual market reach due to natural barriers like rivers and highways. We introduced isochrone drive-time contours to visualize true 5, 10, and 15-minute accessibility zones, aligning our spatial analytics with real-world consumer transit habits."*
- **Manual Test Steps**: Select a store, click "Drive-Time Contours", and observe 3 concentric color-coded polygonal drive-time catchment rings overlaid on the map with estimated population reach.

### Option 2: GeoJSON & CSV Batch Importer with Address Verification
- **Plain English**: Drag-and-drop custom store spreadsheets (CSV or GeoJSON) into the app, with automatic street address geocoding, schema validation, duplicate detection, and instant catalog refresh.
- **Why**: Retail operators have hundreds of locations and cannot enter them one by one through forms. Bulk ingestion with spatial validation is a mandatory enterprise requirement.
- **Trade-off**: Requires boundary error collection (reporting all invalid rows together rather than failing on the first) and rate-limit chunking during batch geocoding.
- **Interview Answer**: *"To enable rapid franchise onboarding, we built a batch CSV and GeoJSON ingestion pipeline. The system validates address schemas, checks for spatial duplicates using coordinate proximity clustering, and chunks external geocoding requests to respect rate limits."*
- **Manual Test Steps**: Drag a sample CSV file with 20 store addresses onto the map, inspect the validation preview table, click "Import", and verify the new locations populate instantly in search and on the map.

### Option 3: Store Inventory & Real-Time Stock Availability Checker
- **Plain English**: Allows shoppers to search for specific product names or SKUs and view which stores have the item in stock, complete with inventory counts, aisle numbers, and reserve-in-store hold requests.
- **Why**: Store locators are most valuable when tied to product availability (BOPIS — Buy Online, Pick Up In Store). Shoppers rarely visit a store without knowing their desired item is on the shelf.
- **Trade-off**: Requires relational tables linking products, store inventory levels, and aisle locations, adding multi-table joins to the repository layer.
- **Interview Answer**: *"Modern retail store locators drive conversion through omnichannel inventory visibility. We integrated product catalog and real-time inventory schemas so users can filter store searches by in-stock SKUs and view specific aisle locations before making the trip."*
- **Manual Test Steps**: Type a product name (e.g., "Wireless Noise-Cancelling Headphones") into the search bar, see store cards filtered to only locations with available stock, and click "Reserve Item" to place a hold.

### Option 4: Turn-by-Turn GPS Navigation Mode with Audio Cue Synthesis
- **Plain English**: A mobile-friendly turn-by-turn driving screen that tracks the user's simulated or live GPS location along the route, auto-advances navigation steps, and speaks voice instructions using Web Speech API.
- **Why**: Transforms the application from a static directory viewer into a full active in-car navigation dashboard.
- **Trade-off**: Requires managing browser audio permissions and simulated GPS coordinate interpolation loops.
- **Interview Answer**: *"To bridge the gap between route planning and in-transit navigation, we implemented an active GPS driving mode. It monitors geolocation updates, snaps coordinates to the active polyline path, and triggers turn-by-turn spoken audio cues via the Web Speech API."*
- **Manual Test Steps**: Open a calculated route, tap "Start Navigation", watch the simulator drive along the route steps, and hear the browser announce *"In 500 feet, turn right onto Market St"*.
