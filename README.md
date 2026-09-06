# Google Maps API Store Locator & Navigation Engine

[![CI](https://github.com/breakingthebot/google-maps-store-locator-build140/actions/workflows/ci.yml/badge.svg)](https://github.com/breakingthebot/google-maps-store-locator-build140/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/Python-3.12%20%7C%203.11%20%7C%203.10-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Framework-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/Tests-68%20Passed%20(100%25)-brightgreen.svg)]()

Production-grade geospatial retail store locator, routing platform, and multi-stop trip planner. Powered by Google Maps Platform APIs (Geocoding, Directions, Places) and an offline-resilient simulation engine. Features Great-Circle Haversine proximity search, spatial bounding-box indexing, real-time operating hours evaluation ("Open Now", "Closing Soon"), Traveling Salesperson Problem (TSP) multi-stop route optimization, quantified mileage savings, cross-platform export (universal Google Maps mobile deep links, scannable QR codes, GPX 1.1, CSV driver manifests, physical print slips), customer rating aggregations, verified reviews, amenity filters, a Rich terminal CLI (`store-locator`), and an interactive single-page map interface.

---

## Architecture Overview

```mermaid
graph TD
    User["Web User / Browser"] -->|HTTP / REST| App["FastAPI Application (src/api/app.py)"]
    CLIUser["Terminal Operator"] -->|CLI Commands| CLI["Rich CLI Suite (src/cli/main.py)"]

    App --> Routes["API Route Controller (src/api/routes.py)"]
    CLI --> ServiceLayer["Service Orchestration Layer"]
    Routes --> ServiceLayer

    subgraph Service Layer
        MapsClient["Google Maps Client (src/services/google_maps.py)"]
        MockMaps["Offline Mock Maps Engine (src/services/mock_maps.py)"]
        Repo["Store Repository (src/services/store_repository.py)"]
        TripPlanner["Trip Planner Service (src/services/trip_planner.py)"]
        TripExporter["Trip Exporter Service (src/services/trip_exporter.py)"]
    end

    subgraph Domain & Calculation Utilities
        Haversine["Haversine Formula & BBox (src/utils/distance.py)"]
        HoursCalc["Operating Hours Engine (src/utils/hours.py)"]
        Polyline["Polyline Encoder/Decoder (src/utils/polyline.py)"]
        Optimizer["TSP Route Optimizer & Matrix (src/utils/optimizer.py)"]
    end

    TripPlanner --> Optimizer
    TripPlanner --> MapsClient
    TripPlanner --> Repo
    TripPlanner --> TripExporter

    MapsClient -.->|Live Key Configured| LiveAPI["Google Maps Platform (Geocoding / Directions)"]
    MapsClient -.->|No Key or Offline| MockMaps

    Repo --> Haversine
    Repo --> HoursCalc
    Optimizer --> Haversine
    TripPlanner --> Polyline
    MapsClient --> Polyline
    MockMaps --> Polyline

    Repo --> SQLite[("SQLite Database (storage/store_locator.db)")]
```

---

## Features

- **Geospatial Proximity Search**: Computes exact Haversine great-circle distances in kilometers and miles. Leverages bounding-box pre-filtering for scalable SQL spatial searches.
- **Multi-Stop Trip Planner & TSP Route Optimization**: Visit 2 to 12 stores in one trip. Uses spatial Traveling Salesperson algorithms (exact brute-force permutation for $N \le 8$, 2-opt heuristic for larger sets) to re-sequence waypoints and eliminate backtracking.
- **Quantified Travel Savings**: Calculates exact mileage, drive time, and percentage distance reductions gained over naive visiting order.
- **Universal Google Maps Mobile Navigation Deep Links**: Constructs official cross-platform URL schemes (`https://www.google.com/maps/dir/?api=1&...`) launching live voice GPS turn-by-turn navigation directly in the native Google Maps app on iOS and Android.
- **Camera-Scannable QR Code Mobile Handoff**: Desktop users can scan an on-screen QR code with their phone camera to beam the optimized multi-stop route directly to their smartphone.
- **GPX 1.1 & CSV Driver Manifest Export**: Generates compliant GPS Exchange Format (`.gpx`) XML for Garmin and in-dash navigation systems, plus tabular CSV driver manifests with stop sequences and physical signature blanks.
- **Physical Print Route Slips (`@media print`)**: Dedicated print stylesheet rendering clean, paper-optimized driver delivery manifests with turn-by-turn route legs and customer sign-off rows.
- **Real-Time Operating Hours & "Open Now" Engine**: Dynamically evaluates weekly 7-day schedules against the current local system clock. Displays "Open until X:XX PM", "Closing soon (Xm left)", and "Closed · Opens tomorrow at X:XX AM".
- **Turn-by-Turn Navigation & Polyline Routing**: Calculates turn-by-turn routing steps with distances, durations, and Google Maps encoded polylines across Driving, Walking, Bicycling, and Transit modes.
- **Zero-Key Offline Mock Simulation Engine**: Runs out of the box with zero external dependencies. Features deterministic geocoding for cities, postal codes, and landmarks, and simulated turn-by-turn routing when no Google Cloud billing key is provided.
- **Rich Command-Line Suite (`store-locator`)**: Complete terminal tool for proximity searching, multi-stop trip planning (`store-locator trip`), store profile inspection, routing, route export (`--export-gpx`, `--export-csv`), and server execution.
- **Interactive Responsive Map Interface**: Standalone web UI with custom map pins color-coded by open/closed status, user radar location, search autocomplete, radius controls, multi-amenity filter chips, floating multi-stop trip drawer, and store details modal.
- **Automated Verification**: Comprehensive 68-test suite covering spatial geometry, operating hours boundary conditions, mock engines, TSP route optimization, route export, REST endpoints, and CLI flows.

---

## Tech Stack

- **Language**: Python 3.12 (compatible with 3.10+)
- **Web Framework**: FastAPI, Uvicorn, Starlette
- **Data Validation & Schemas**: Pydantic v2, Pydantic Settings
- **HTTP Client**: HTTPX (async client with retry policies)
- **CLI & Formatting**: Click, Rich
- **Testing**: Pytest, Pytest-Asyncio
- **Frontend**: Vanilla JavaScript (ES6+), HTML5 Geolocation, Responsive CSS3, SVG Geospatial Map Canvas

---

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Git

### Installation

```bash
# 1. Clone repository
git clone https://github.com/breakingthebot/google-maps-store-locator-build140.git
cd google-maps-store-locator-build140

# 2. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate          # Windows PowerShell / CMD
# source venv/bin/activate     # macOS / Linux

# 3. Install dependencies in editable mode
pip install -e .
```

---

## Running Locally

### 1. Launch Web Server

```bash
store-locator serve --port 8000
```
Open your browser at **`http://localhost:8000`** to access the interactive store locator and route planner.

### 2. CLI Command Examples

```bash
# Verify CLI tool and version
store-locator --version

# Proximity search near San Francisco
store-locator search --address "San Francisco" --radius 20 --open-now

# View detailed store profile, weekly schedule, amenities, and reviews
store-locator get 1

# Calculate turn-by-turn route
store-locator directions --from-loc "760 Market St" --to-store 1 --mode driving

# Plan an optimized multi-stop trip visiting stores 1, 2, and 4
store-locator trip --origin "Market St" -s 1 -s 2 -s 4 --round-trip

# Plan trip and export GPX file + CSV driver manifest
store-locator trip --origin "Market St" -s 1 -s 3 -s 5 --export-gpx my_route.gpx --export-csv manifest.csv

# List registered stores
store-locator list --limit 10
```

---

## REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | System health, database connection, and Maps provider status |
| `GET` | `/api/config` | Public frontend configuration and default coordinates |
| `GET` | `/api/geocode` | Geocode an address query or reverse geocode lat/lng |
| `GET` | `/api/stores/search` | Spatial proximity search with amenity & open-now filters |
| `GET` | `/api/stores/{id}` | Store details with full weekly schedule and customer reviews |
| `POST` | `/api/stores` | Register a new retail store location |
| `GET` | `/api/directions` | Single turn-by-turn navigation route, steps, and polyline |
| `POST` | `/api/trip/plan` | Plan multi-stop trip with TSP waypoint optimization and savings |
| `GET` | `/api/trip/preview` | Quick multi-stop preview endpoint |
| `POST` | `/api/trip/export/gpx` | Export trip itinerary as GPS Exchange Format (GPX 1.1) XML |
| `POST` | `/api/trip/export/csv` | Export trip itinerary as tabular CSV driver delivery manifest |
| `POST` | `/api/trip/export/url` | Generate universal Google Maps mobile navigation deep link |

---

## Data Handling & Privacy

- **Data Posture**: Store locator queries and geolocation requests are ephemeral and processed in-memory.
- **Zero PII Storage**: End-user search queries, GPS coordinates, and routing requests are never written to disk or database tables.
- **Redacted Logging**: All external HTTP requests to Google Maps Platform strictly mask and redact API keys (`***REDACTED***`).
- **Data Persistence**: Only retail store facility catalog records (store name, public street address, operating hours, amenities, public reviews) are persisted in `storage/store_locator.db`.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
