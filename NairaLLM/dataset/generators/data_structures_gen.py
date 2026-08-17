"""
Data Structures Domain Generator for Dataset A.
Generates comprehensive technical prose on advanced data structures, self-balancing trees, hash tables, heaps, and probabilistic structures.
"""

from __future__ import annotations

from typing import Any


def get_data_structures_samples() -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []

    def add(sample_id: str, text: str, notes: str = "") -> None:
        samples.append({
            "id": sample_id,
            "domain": "data_structures",
            "language": "en",
            "text": text.strip(),
            "provenance": {
                "provenance_id": f"prov_{sample_id}",
                "author": "nairallm_semantic_curator",
                "license": "Apache-2.0",
                "acquisition_method": "controlled_synthetic",
                "notes": notes or "Data structures theory and memory layout exposition",
            },
        })

    add(
        "sem_ds_001",
        "Red-Black Trees are self-balancing binary search trees that guarantee O(log N) worst-case time complexity for search, insertion, and deletion operations. Every node is colored either red or black, constrained by five strict properties: the root is black, all NIL leaves are black, if a node is red then both its children are black (no adjacent red nodes), and every path from a node to any descendant leaf contains the same number of black nodes (black-height). Tree balance is restored after insertions via node recoloring and single or double tree rotations.",
        "Red-Black Tree balance invariants and rotation mechanics",
    )

    add(
        "sem_ds_002",
        "Hash tables provide average O(1) time complexity for insertion, lookup, and deletion by mapping keys to array bucket indices via a hash function. Collision resolution strategies include Separate Chaining (where each bucket contains a linked list or red-black tree of colliding entries) and Open Addressing (where colliding keys are placed in alternative probe slots). Robin Hood hashing is an advanced open-addressing technique that steals slots from 'rich' keys (keys close to their initial hash bucket) to reduce variance in probe sequence lengths for 'poor' keys.",
        "Hash table collision resolution (Separate Chaining vs Robin Hood Hashing)",
    )

    add(
        "sem_ds_003",
        "A Trie (Prefix Tree) is an ordered tree data structure used to store associative arrays where keys are usually strings. Unlike binary search trees where keys are compared in their entirety at each node, no node in a trie stores the key associated with that node; instead, its position in the tree defines the associated string key. Tries enable prefix matching, autocomplete lookups, spell checking, and longest-prefix IP routing table lookups in O(K) time, where K is key length.",
        "Trie prefix tree data structure and autocomplete lookups",
    )

    add(
        "sem_ds_004",
        "Segment Trees are binary tree data structures used for storing intervals or segments, allowing efficient logarithmic O(log N) range queries (such as range minimum, range sum, or range greatest common divisor) and point/range updates on an array of N elements. When combined with Lazy Propagation, segment trees defer updates to child nodes until necessary, enabling O(log N) updates over arbitrary contiguous ranges rather than updating individual leaves one-by-one.",
        "Segment Tree data structure with Lazy Propagation for range queries",
    )

    add(
        "sem_ds_005",
        "A Binary Heap is a complete binary tree that satisfies the heap property: in a Min-Heap, the key at the root is the minimum among all keys in the tree, and the same property recursively holds for all subtrees. Because binary heaps are structurally complete trees, they can be efficiently represented as contiguous flat arrays where for an element at index i, its parent resides at index (i - 1) // 2, left child at 2i + 1, and right child at 2i + 2. Heaps support extract-min in O(log N) and heap construction in O(N).",
        "Binary heap array representation and heapify mechanics",
    )

    add(
        "sem_ds_006",
        "Bloom Filters are space-efficient probabilistic data structures used to test whether an element is a member of a set. False positive query results are possible (a query may report an item is present when it was not inserted), but false negatives are impossible (if the filter reports an item is absent, it is definitively not present). An empty Bloom filter is a bit array of m bits, all initialized to 0, accompanied by k independent cryptographic hash functions that set bits upon element addition.",
        "Bloom filter probabilistic membership and false positive math",
    )

    add(
        "sem_ds_007",
        "Disjoint-Set Union (DSU), also known as the Union-Find data structure, maintains a collection of disjoint dynamic sets. It supports two primary operations: Find (determines which subset a particular element belongs to) and Union (joins two subsets into a single subset). When optimized with both Path Compression (flattening tree structure during find) and Union by Rank (attaching smaller trees under larger tree roots), DSU operations execute in near-constant O(alpha(N)) amortized time, where alpha is the inverse Ackermann function.",
        "Disjoint-Set Union (Union-Find) with path compression and rank union",
    )

    add(
        "sem_ds_008",
        "Skip Lists are probabilistic alternatives to balanced binary search trees that allow O(log N) search and insertion within an ordered sequence of elements. A skip list is constructed in layers: the bottom layer is an ordinary sorted linked list containing all elements, and each higher layer acts as an 'express lane' containing a subset of the elements from the layer below, with elements promoted to higher levels based on coin flips.",
        "Skip List probabilistic multi-level search structure",
    )

    add(
        "sem_ds_009",
        "Circular Buffers (Ring Buffers) are fixed-size data structures connected end-to-end that operate as first-in, first-out (FIFO) queues. Maintained via two integer pointers or indices (head for reading and tail for writing), circular buffers wrap around to the beginning of the memory array modulo the buffer capacity. Because they require no dynamic memory allocation or element shifting during push and pop operations, ring buffers are standard in low-latency audio processing, network packet queues, and inter-thread lock-free queues.",
        "Circular ring buffer fixed-size FIFO queues and lock-free concurrency",
    )

    add(
        "sem_ds_010",
        "Fenwick Trees, or Binary Indexed Trees (BIT), are compact data structures that maintain a sequence of numbers and calculate running prefix sums in O(log N) time, while allowing point updates in O(log N) time. Unlike Segment Trees which require 4N space, a Fenwick Tree requires only N storage elements and leverages binary two's complement bitwise arithmetic (isolating the lowest set bit via `i & (-i)`) to traverse parent and child relationships rapidly.",
        "Fenwick Tree (Binary Indexed Tree) prefix sums and bitwise index math",
    )

    return samples
