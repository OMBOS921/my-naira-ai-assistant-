"""
Expanded Algorithms & Data Structures Domain Generator for Dataset A.
Generates comprehensive algorithm walkthroughs on sorting, graph algorithms, dynamic programming, and computational geometry.
"""

from __future__ import annotations

from typing import Any


def get_algorithms_expanded_samples() -> list[dict[str, Any]]:
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
                "notes": notes or "Expanded algorithm analysis and computational walkthrough",
            },
        })

    add(
        "sem_algo_011",
        "Topological Sorting of a Directed Acyclic Graph (DAG) produces a linear ordering of vertices such that for every directed edge (u, v), vertex u appears before vertex v in the ordering. Kahn's Algorithm computes topological order using in-degree counters: it initializes a queue containing all vertices with in-degree 0, repeatedly dequeues a vertex, appends it to the topological sort result, and decrements the in-degree of its adjacent neighbors, adding any neighbor that reaches in-degree 0 to the queue. If the final output contains fewer than V vertices, the graph contains a cycle.",
        "Kahn algorithm for topological sorting in DAGs",
    )

    add(
        "sem_algo_012",
        "Kruskal's algorithm finds a Minimum Spanning Tree (MST) in a connected, weighted graph by sorting all edges in non-decreasing order of weight and greedily adding edges that do not form a cycle. Cycle detection is executed efficiently in near-constant time using the Disjoint-Set Union (DSU / Union-Find) data structure with path compression. The algorithm processes edges until V - 1 edges have been included in the spanning forest, running in O(E log E) time dominated by the edge sorting phase.",
        "Kruskal Minimum Spanning Tree algorithm with Disjoint-Set Union",
    )

    add(
        "sem_algo_013",
        "The Bellman-Ford algorithm computes single-source shortest paths in weighted graphs that may contain negative edge weights. The algorithm operates by relaxing all E edges in the graph V - 1 times, guaranteeing that shortest paths up to length V - 1 edges are correctly computed. A subsequent V-th relaxation pass checks if any distance can still be reduced; if so, the graph contains a negative-weight cycle reachable from the source, rendering shortest path metrics undefined.",
        "Bellman-Ford shortest path algorithm and negative cycle detection",
    )

    add(
        "sem_algo_014",
        "Convex Hull algorithms find the smallest convex polygon that encloses a set of 2D points. Graham's Scan algorithm solves the convex hull problem in O(N log N) time by initially finding the point with the lowest y-coordinate (anchor), sorting all remaining points by polar angle with respect to the anchor, and sequentially pushing points onto a stack while performing 2D cross-product orientation tests to discard points that make non-left turns.",
        "Graham Scan 2D convex hull algorithm and cross-product orientation tests",
    )

    return samples
