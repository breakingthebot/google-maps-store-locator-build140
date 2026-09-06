# tests/test_optimizer.py
# Unit tests for Travelling Salesperson Problem (TSP) spatial route optimizer.
# Connects to: src/utils/optimizer.py, src/utils/distance.py
# Created: 2026-09-06

import pytest
from src.utils.optimizer import (
    compute_distance_matrix,
    compute_tour_distance,
    optimize_route,
    solve_tsp_2opt,
    solve_tsp_bruteforce,
)


def test_compute_distance_matrix() -> None:
    coords = [
        (37.774929, -122.419416),  # SF Civic Center
        (37.785834, -122.406417),  # Market St
        (37.759865, -122.414798),  # Mission St
    ]
    matrix = compute_distance_matrix(coords)
    assert len(matrix) == 3
    assert len(matrix[0]) == 3
    # Diagonal is zero
    assert matrix[0][0] == 0.0
    assert matrix[1][1] == 0.0
    assert matrix[2][2] == 0.0
    # Symmetric
    assert matrix[0][1] == matrix[1][0]
    assert matrix[1][2] == matrix[2][1]
    assert matrix[0][1] > 0.5  # Real distance is around 1.5 km


def test_compute_tour_distance() -> None:
    matrix = [
        [0.0, 10.0, 20.0],
        [10.0, 0.0, 5.0],
        [20.0, 5.0, 0.0],
    ]
    # One-way 0 -> 1 -> 2: 10 + 5 = 15
    assert compute_tour_distance([0, 1, 2], matrix, round_trip=False) == 15.0
    # Round-trip 0 -> 1 -> 2 -> 0: 10 + 5 + 20 = 35
    assert compute_tour_distance([0, 1, 2], matrix, round_trip=True) == 35.0


def test_solve_tsp_bruteforce_optimality() -> None:
    # 4 collinear points along latitude: 0, 1, 2, 3
    # If visited out of order: 0 -> 3 -> 1 -> 2, distance is much worse than 0 -> 1 -> 2 -> 3
    coords = [
        (37.70, -122.40),  # Node 0
        (37.72, -122.40),  # Node 1
        (37.75, -122.40),  # Node 2
        (37.79, -122.40),  # Node 3
    ]
    matrix = compute_distance_matrix(coords)
    tour, dist = solve_tsp_bruteforce(matrix, round_trip=False)
    # The optimal one-way tour along a line must be in monotonic order [0, 1, 2, 3]
    assert tour == [0, 1, 2, 3]


def test_solve_tsp_2opt_efficiency() -> None:
    # Circle of 6 points
    coords = [
        (37.7749, -122.4194),
        (37.7800, -122.4100),
        (37.7850, -122.4000),
        (37.7800, -122.3900),
        (37.7700, -122.3900),
        (37.7650, -122.4100),
    ]
    matrix = compute_distance_matrix(coords)
    tour, dist = solve_tsp_2opt(matrix, round_trip=True)
    assert len(tour) == 6
    assert tour[0] == 0
    assert dist > 0


def test_optimize_route_savings_on_scrambled_stops() -> None:
    # Provide coordinates in scrambled zigzag order:
    # Node 0 (Origin), Node 1 (Far north), Node 2 (Near origin), Node 3 (Very far north)
    coords = [
        (37.70, -122.40),  # 0: Origin
        (37.85, -122.40),  # 1: Far North
        (37.72, -122.40),  # 2: Near South
        (37.88, -122.40),  # 3: Far North
    ]
    best_tour, opt_dist, naive_dist = optimize_route(coords, round_trip=False)
    # Optimized must beat the zig-zag naive order
    assert opt_dist <= naive_dist
    assert best_tour[0] == 0


def test_optimize_route_edge_cases() -> None:
    # Single node
    tour, opt_d, naive_d = optimize_route([(37.7, -122.4)])
    assert tour == [0]
    assert opt_d == 0.0

    # Two nodes
    tour, opt_d, naive_d = optimize_route([(37.7, -122.4), (37.8, -122.4)], round_trip=False)
    assert tour == [0, 1]
    assert opt_d > 0.0
