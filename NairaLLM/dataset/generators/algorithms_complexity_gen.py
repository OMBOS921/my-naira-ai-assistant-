"""
Algorithms & Computational Complexity Domain Generator for Dataset A.
Generates comprehensive technical prose on asymptotic analysis, dynamic programming, graph algorithms, divide-and-conquer, and string searching.
"""

from __future__ import annotations

from typing import Any


def get_algorithms_complexity_samples() -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []

    def add(sample_id: str, text: str, notes: str = "") -> None:
        samples.append({
            "id": sample_id,
            "domain": "algorithms",
            "language": "en",
            "text": text.strip(),
            "provenance": {
                "provenance_id": f"prov_{sample_id}",
                "author": "nairallm_semantic_curator",
                "license": "Apache-2.0",
                "acquisition_method": "controlled_synthetic",
                "notes": notes or "Algorithms and complexity theory technical exposition",
            },
        })

    add(
        "sem_algo_001",
        "Asymptotic notation provides a mathematical language for describing the limiting behavior of algorithmic execution time or memory consumption as input size N grows toward infinity. Big-O notation (O) establishes an asymptotic upper bound, characterizing worst-case performance. Big-Omega (Ω) defines an asymptotic lower bound, representing the best-case floor. Big-Theta (Θ) provides a tight bound when upper and lower bounds coincide. For instance, Merge Sort has a tight complexity of Θ(N log N) in all cases.",
        "Asymptotic complexity notation (Big-O, Big-Omega, Big-Theta)",
    )

    add(
        "sem_algo_002",
        "Dynamic Programming (DP) solves complex optimization problems by breaking them down into overlapping subproblems and optimal substructure properties. There are two primary implementation paradigms: Top-Down DP with Memoization (which uses recursion while caching subproblem results in a hash table or array) and Bottom-Up DP with Tabulation (which iteratively fills a table from base cases upward). Classic DP problems include the 0/1 Knapsack problem, Longest Common Subsequence (LCS), and Levenshtein Edit Distance.",
        "Dynamic programming paradigms (Memoization vs Tabulation)",
    )

    add(
        "sem_algo_003",
        "Dijkstra's algorithm finds the shortest paths from a single source node to all other vertices in a directed or undirected graph with non-negative edge weights. Using a min-priority queue (such as a binary or Fibonacci heap) to greedily extract the unvisited vertex with the smallest tentative distance, the algorithm relaxes adjacent outgoing edges. With an adjacency list and binary heap, Dijkstra executes in O((V + E) log V) time, where V is vertices and E is edges.",
        "Dijkstra shortest path algorithm with priority queues",
    )

    add(
        "sem_algo_004",
        "Divide-and-Conquer algorithms solve computational problems by recursively dividing the original problem into two or more smaller subproblems of the same type, solving the subproblems independently, and combining their results. The Master Theorem provides a cookbook method for determining asymptotic runtime for recurrence relations of the form T(N) = a T(N/b) + f(N), classifying solutions based on comparing f(N) with N^(log_b a).",
        "Divide-and-conquer paradigm and the Master Theorem",
    )

    add(
        "sem_algo_005",
        "A* (A-Star) search is a graph traversal and pathfinding algorithm widely used in autonomous navigation and game development. A* enhances Dijkstra's algorithm by using a heuristic function h(n) that estimates the cost from current node n to the goal. It prioritizes exploration of nodes with minimal total evaluation function f(n) = g(n) + h(n), where g(n) is the exact cost from the start node. When h(n) is admissible (never overestimates true cost) and consistent, A* is mathematically guaranteed to return the optimal shortest path.",
        "A-Star search algorithm and admissible heuristics",
    )

    add(
        "sem_algo_006",
        "The Knuth-Morris-Pratt (KMP) string matching algorithm searches for occurrences of a pattern string P within a text T in linear O(N + M) time. Unlike naive brute-force string search which backtracks in the text upon encountering a character mismatch, KMP precomputes a Longest Prefix Suffix (LPS) array from the pattern. The LPS table encodes the length of the longest proper prefix of the pattern that is also a suffix, allowing the search pointer in text T to advance without ever moving backwards.",
        "Knuth-Morris-Pratt (KMP) string search and prefix function LPS array",
    )

    add(
        "sem_algo_007",
        "Tarjan's algorithm finds all Strongly Connected Components (SCCs) in a directed graph in a single Depth-First Search (DFS) pass in linear O(V + E) time. An SCC is a maximal subgraph wherein every vertex is reachable from every other vertex. As Tarjan's algorithm traverses the graph, it maintains DFS discovery times and a 'low-link' value for each vertex, representing the lowest discovery time reachable from that node via back-edges, using a stack to isolate SCC subgraphs.",
        "Tarjan algorithm for Strongly Connected Components in directed graphs",
    )

    add(
        "sem_algo_008",
        "Quickselect is a selection algorithm designed to find the k-th smallest element in an unordered list in average-case O(N) time without sorting the entire array. Operating similarly to Quicksort, Quickselect chooses a pivot element and partitions the array into elements smaller than and larger than the pivot. Rather than recurring on both partitions, Quickselect inspects the pivot's final index and recurs only into the single partition containing index k.",
        "Quickselect algorithm for k-th order statistics in linear time",
    )

    add(
        "sem_algo_009",
        "The Floyd-Warshall algorithm is an all-pairs shortest path dynamic programming algorithm that finds the shortest paths between all pairs of vertices in a weighted graph, even with negative edge weights (provided no negative cycles exist). It iteratively considers whether routing through an intermediate vertex k produces a shorter path between vertices i and j: dist[i][j] = min(dist[i][j], dist[i][k] + dist[k][j]), operating in O(V^3) time with O(V^2) matrix space.",
        "Floyd-Warshall all-pairs shortest path dynamic programming algorithm",
    )

    add(
        "sem_algo_010",
        "NP-Completeness is a foundational concept in computational complexity theory describing decision problems that are in NP (nondeterministic polynomial time, solutions can be verified in polynomial time) and are NP-hard (every problem in NP can be polynomial-time reduced to them). If any single NP-complete problem—such as Boolean Satisfiability (SAT), Traveling Salesperson (TSP), or Graph 3-Coloring—can be solved in polynomial time, then P = NP.",
        "NP-Completeness, polynomial time reductions, and the P vs NP problem",
    )

    return samples
