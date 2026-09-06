# src/utils/optimizer.py
# Traveling Salesperson Problem (TSP) spatial route optimizer and distance matrix solver.
# Connects to: src/utils/distance.py, src/models/trip.py, src/services/trip_planner.py
# Created: 2026-09-06

import itertools
import math
from typing import List, Tuple
from src.utils.distance import haversine_distance_km


def compute_distance_matrix(coordinates: List[Tuple[float, float]]) -> List[List[float]]:
    """Generate an N x N symmetric pairwise distance matrix in kilometers.

    Args:
        coordinates: List of (latitude, longitude) tuples.

    Returns:
        Square 2D matrix of pairwise Haversine distances in kilometers.
    """
    n = len(coordinates)
    matrix = [[0.0] * n for _ in range(n)]

    for i in range(n):
        lat1, lon1 = coordinates[i]
        for j in range(i + 1, n):
            lat2, lon2 = coordinates[j]
            dist = haversine_distance_km(lat1, lon1, lat2, lon2)
            matrix[i][j] = dist
            matrix[j][i] = dist

    return matrix


def compute_tour_distance(tour: List[int], dist_matrix: List[List[float]], round_trip: bool = True) -> float:
    """Calculate the total cumulative distance of a given tour order.

    Args:
        tour: Chronological sequence of node indices, starting at index 0.
        dist_matrix: Precomputed pairwise distance matrix.
        round_trip: If True, adds distance from last stop back to starting node 0.

    Returns:
        Total distance in kilometers.
    """
    if len(tour) < 2:
        return 0.0

    total = 0.0
    for i in range(len(tour) - 1):
        total += dist_matrix[tour[i]][tour[i + 1]]

    if round_trip and len(tour) > 1:
        total += dist_matrix[tour[-1]][tour[0]]

    return round(total, 4)


def solve_tsp_bruteforce(dist_matrix: List[List[float]], round_trip: bool = True) -> Tuple[List[int], float]:
    """Find the mathematically exact optimal visiting order via exhaustive permutation search.

    Suitable for N <= 9 total locations (origin + up to 8 stores).

    Args:
        dist_matrix: Pairwise distance matrix.
        round_trip: Whether to include return leg back to origin (node 0).

    Returns:
        Tuple of (optimal_tour_indices, minimal_total_distance_km).
    """
    n = len(dist_matrix)
    if n <= 1:
        return list(range(n)), 0.0
    if n == 2:
        tour = [0, 1]
        return tour, compute_tour_distance(tour, dist_matrix, round_trip)

    # Origin node is fixed at position 0. Permute intermediate stops [1, 2, ..., n-1].
    intermediate_stops = list(range(1, n))
    best_tour = [0] + intermediate_stops
    best_dist = compute_tour_distance(best_tour, dist_matrix, round_trip)

    for perm in itertools.permutations(intermediate_stops):
        candidate_tour = [0] + list(perm)
        candidate_dist = compute_tour_distance(candidate_tour, dist_matrix, round_trip)
        if candidate_dist < best_dist:
            best_dist = candidate_dist
            best_tour = candidate_tour

    return best_tour, best_dist


def solve_tsp_2opt(dist_matrix: List[List[float]], round_trip: bool = True, max_iterations: int = 500) -> Tuple[List[int], float]:
    """Heuristic TSP solver combining greedy Nearest-Neighbor initialization with 2-opt edge swapping.

    Scales efficiently for larger node sets while producing near-optimal tours.

    Args:
        dist_matrix: Pairwise distance matrix.
        round_trip: Whether to include return leg back to origin (node 0).
        max_iterations: Maximum 2-opt improvement passes before termination.

    Returns:
        Tuple of (optimized_tour_indices, total_distance_km).
    """
    n = len(dist_matrix)
    if n <= 2:
        return list(range(n)), compute_tour_distance(list(range(n)), dist_matrix, round_trip)

    # Step 1: Greedy Nearest Neighbor initialization starting at node 0
    unvisited = set(range(1, n))
    current_node = 0
    tour = [current_node]

    while unvisited:
        nearest_node = min(unvisited, key=lambda node: dist_matrix[current_node][node])
        tour.append(nearest_node)
        unvisited.remove(nearest_node)
        current_node = nearest_node

    best_tour = tour
    best_dist = compute_tour_distance(best_tour, dist_matrix, round_trip)

    # Step 2: 2-opt edge swap refinement
    improved = True
    iteration = 0

    while improved and iteration < max_iterations:
        improved = False
        iteration += 1

        for i in range(1, n - 1):
            for j in range(i + 1, n):
                # Reverse sub-tour between index i and j
                new_tour = best_tour[:i] + best_tour[i:j + 1][::-1] + best_tour[j + 1:]
                new_dist = compute_tour_distance(new_tour, dist_matrix, round_trip)

                if new_dist < best_dist - 1e-6:
                    best_tour = new_tour
                    best_dist = new_dist
                    improved = True
                    break
            if improved:
                break

    return best_tour, round(best_dist, 4)


def optimize_route(coordinates: List[Tuple[float, float]], round_trip: bool = True) -> Tuple[List[int], float, float]:
    """Optimize waypoint sequence to minimize total route travel distance.

    Args:
        coordinates: List of (lat, lon) coordinates, where coordinates[0] is the starting origin.
        round_trip: Whether tour loops back to coordinates[0].

    Returns:
        Tuple of (optimal_tour_indices, optimized_distance_km, naive_input_distance_km).
    """
    if len(coordinates) <= 1:
        return [0], 0.0, 0.0

    dist_matrix = compute_distance_matrix(coordinates)
    naive_order = list(range(len(coordinates)))
    naive_distance = compute_tour_distance(naive_order, dist_matrix, round_trip)

    # For N <= 9 nodes (1 origin + up to 8 waypoints), exact brute force finishes in < 25ms.
    if len(coordinates) <= 9:
        best_tour, optimized_distance = solve_tsp_bruteforce(dist_matrix, round_trip)
    else:
        best_tour, optimized_distance = solve_tsp_2opt(dist_matrix, round_trip)

    return best_tour, optimized_distance, naive_distance
