# Iterations & Git Commit Log

**Project**: Google Maps API Store Locator & Directions Engine (Build 140)  
**Repository**: [https://github.com/breakingthebot/google-maps-store-locator-build140](https://github.com/breakingthebot/google-maps-store-locator-build140)  
**Stack**: Python 3.12, FastAPI, SQLite, Pydantic v2, HTTPX, Click, Rich, Pytest, Vanilla JS / Responsive CSS  

This document logs every incremental engineering iteration and git commit pushed to the public repository.

---

## Iteration Overview Table

| Iteration | Git Commit | Version | Focus / Summary | Tests Passed | Full Summary Archive |
| :---: | :---: | :---: | :--- | :---: | :--- |
| **01** | [`1cf3d21`](https://github.com/breakingthebot/google-maps-store-locator-build140/commit/1cf3d21) | `v1.0.0` | **Core Google Maps Platform Integration, Haversine Proximity Search, Real-Time Operating Hours, Turn-by-Turn Navigation & Interactive Map UI**<br>Complete domain models, Haversine distance and bounding box calculations, live operating hours engine ("Open Now", "Closing Soon"), Google Maps Platform HTTP client with retry policies, high-fidelity offline mock maps engine, SQLite store repository with 16 pre-seeded locations, FastAPI REST API, installable Rich CLI suite (`store-locator`), responsive map UI with directions drawer, and multi-version CI workflow. | 40 / 40 | [Iteration 01 Summary](docs/summaries/iteration_01_summary.md) |
| **02** | [`9c9ed6a`](https://github.com/breakingthebot/google-maps-store-locator-build140/commit/9c9ed6a) | `v1.1.0` | **Multi-Stop Trip Planner & Route Optimization (TSP)**<br>Traveling Salesperson Problem (TSP) spatial optimizer with distance matrix generation, exact brute-force permutation solver and 2-opt heuristic, quantified mileage/time savings metrics, `TripPlannerService`, `POST /api/trip/plan` & `GET /api/trip/preview` endpoints, `store-locator trip` CLI command, floating trip cart bar, multi-stop itinerary modal, and composite multi-leg polyline rendering. | 56 / 56 | [Iteration 02 Summary](docs/summaries/iteration_02_summary.md) |

---

## Chronological Iteration Entries

### Iteration 1: Core Google Maps Platform Integration, Haversine Proximity Search, Real-Time Operating Hours, Turn-by-Turn Navigation & Interactive Map UI
- **Git Commit**: [`1cf3d21`](https://github.com/breakingthebot/google-maps-store-locator-build140/commit/1cf3d21)
- **Tag / Version**: `v1.0.0`
- **Date**: 2026-09-06
- **Plain English Summary**:
  Built a comprehensive Google Maps Platform store locator and navigation engine. The platform provides great-circle Haversine proximity search with bounding-box SQL spatial pre-filtering, a real-time business hours engine calculating "Open Now" and "Closing Soon" states against 7-day weekly schedules, and turn-by-turn routing with Google Maps encoded polylines across multiple travel modes. Designed with a resilient dual-engine architecture: when a live Google Maps Platform key is configured, it queries official Google Geocoding, Directions, and Places endpoints with exponential backoff on 429/5xx errors; when offline or keyless, an offline simulation engine provides deterministic geocoding and routing without external dependencies. Features an SQLite repository pre-seeded with 16 flagship retail branches, a full FastAPI REST API, an installable Click/Rich CLI suite (`store-locator`), and a responsive single-page web application with interactive map rendering, user radar geolocation, filter chips, directions drawer, and store modal.

### Iteration 2: Multi-Stop Trip Planner & Route Optimization (TSP)
- **Git Commit**: [`9c9ed6a`](https://github.com/breakingthebot/google-maps-store-locator-build140/commit/9c9ed6a)
- **Tag / Version**: `v1.1.0`
- **Date**: 2026-09-06
- **Plain English Summary**:
  Engineered an intelligent Multi-Stop Trip Planner that solves the Traveling Salesperson Problem (TSP) for visiting multiple store locations in one outing. Implemented an exact brute-force permutation optimizer for sets of up to 8 stores and a 2-opt local search heuristic for larger sets, eliminating erratic zig-zagging and backtracking. Quantified travel efficiency gains by calculating exact miles and minutes saved compared to naive visit sequences. Exposed the feature via `POST /api/trip/plan` and `GET /api/trip/preview`, an enhanced `store-locator trip` CLI command, a floating bottom trip planner bar, store card "+ Trip" toggle buttons, a full Multi-Stop Itinerary modal with savings banner, and composite multi-leg polyline rendering on the interactive SVG canvas map. Expanded test suite to 56 passing tests (100% pass rate).

