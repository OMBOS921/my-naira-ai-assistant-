"""
Databases & Storage Systems Domain Generator for Dataset A.
Generates comprehensive technical prose on relational ACID theory, B+ Trees vs LSM Trees, query optimization, isolation levels, and NoSQL paradigms.
"""

from __future__ import annotations

from typing import Any


def get_databases_storage_samples() -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []

    def add(sample_id: str, text: str, notes: str = "") -> None:
        samples.append({
            "id": sample_id,
            "domain": "databases",
            "language": "en",
            "text": text.strip(),
            "provenance": {
                "provenance_id": f"prov_{sample_id}",
                "author": "nairallm_semantic_curator",
                "license": "Apache-2.0",
                "acquisition_method": "controlled_synthetic",
                "notes": notes or "Databases and storage engine internals exposition",
            },
        })

    add(
        "sem_db_001",
        "B+ Tree index structures are the primary storage abstraction for relational database management systems like PostgreSQL and MySQL InnoDB. A B+ Tree is a self-balancing N-ary search tree where all data records or heap row pointers reside exclusively in leaf nodes, while internal nodes contain only search keys and child page pointers. Leaf nodes are linked contiguously in a doubly-linked list, facilitating high-speed O(log N) point lookups and efficient sequential range scans across disk blocks.",
        "B+ Tree index structures and range scan mechanics",
    )

    add(
        "sem_db_002",
        "Log-Structured Merge-Trees (LSM-Trees) are optimized for high-throughput write-intensive workloads in distributed NoSQL databases such as Apache Cassandra, RocksDB, and ScyllaDB. Incoming writes are appended sequentially to a Write-Ahead Log (WAL) for durability and inserted into an in-memory sorted structure called a MemTable. When the MemTable fills, it is flushed immutably to disk as a Sorted String Table (SSTable). Background compaction threads merge overlapping SSTables, purging tombstones and resolving duplicates.",
        "LSM-Tree storage architecture (MemTable, SSTable, Compaction)",
    )

    add(
        "sem_db_003",
        "Write-Ahead Logging (WAL) is the fundamental mechanism guaranteeing Atomicity and Durability in ACID-compliant databases. Before any modified page or record in memory (a dirty buffer) is written to the persistent database table file, the corresponding log record describing the delta must be flushed to the sequential WAL on disk. In the event of an unannounced power failure or kernel panic, the database recovery manager replays the WAL to REDO committed transactions and UNDO uncommitted operations (ARIES recovery protocol).",
        "Write-Ahead Logging (WAL) and ARIES crash recovery",
    )

    add(
        "sem_db_004",
        "ANSI SQL transaction isolation levels define the degree to which concurrent transactions are shielded from each other's intermediate state. Read Uncommitted allows dirty reads (reading uncommitted changes). Read Committed prevents dirty reads using short-lived read locks or snapshot views. Repeatable Read prevents non-repeatable reads by ensuring rows read once retain identical values throughout the transaction. Serializable, the strictest level, prevents phantom reads and guarantees execution equivalent to a strict serial schedule.",
        "SQL isolation levels and concurrency anomalies (Dirty Read, Phantom Read)",
    )

    add(
        "sem_db_005",
        "Multi-Version Concurrency Control (MVCC) enables databases to achieve high read and write concurrency without locking entire tables. In MVCC engines like PostgreSQL, each row modification creates a new tuple version tagged with transaction creation and expiration identifiers (xmin/xmax). Readers access a consistent snapshot corresponding to the database state at the beginning of their transaction, allowing reads to never block writes and writes to never block reads. Background VACUUM processes reclaim dead tuple versions.",
        "MVCC concurrency control and tuple versioning in PostgreSQL",
    )

    add(
        "sem_db_006",
        "Relational database query planners employ cost-based optimization (CBO) to convert declarative SQL queries into efficient physical execution plans. The optimizer analyzes catalog statistics—such as table cardinality, column histograms, index selectivity, and page counts—to choose among physical join algorithms: Nested Loop Join (efficient for small indexed outer sets), Hash Join (ideal for large equi-joins where an in-memory hash table fits in RAM), or Sort-Merge Join (optimal when both inputs are pre-sorted).",
        "Cost-based query optimization and physical join algorithms",
    )

    add(
        "sem_db_007",
        "Database sharding is a horizontal partitioning strategy used to scale databases beyond the storage and compute limits of a single server. In a sharded database, the dataset is divided into smaller subsets called shards, distributed across distinct database nodes. Sharding strategies include Hash-based sharding (distributes rows evenly via a hash of the shard key), Range-based sharding (allocates contiguous key ranges), and Directory-based sharding (utilizes a central lookup service).",
        "Database horizontal sharding strategies and partition keys",
    )

    add(
        "sem_db_008",
        "Two-Phase Commit (2PC) is a distributed algorithm that coordinates all participating nodes in a distributed database to commit or abort a transaction atomically. In the Prepare Phase, the coordinator sends a Prepare query to all cohort nodes; each cohort executes the transaction locally up to the commit point, writes UNDO/REDO logs, and votes YES or NO. In the Commit Phase, if all cohorts voted YES, the coordinator broadcasts a GLOBAL_COMMIT message; if any cohort voted NO or timed out, a GLOBAL_ABORT is broadcast.",
        "Two-Phase Commit (2PC) atomic distributed transaction protocol",
    )

    add(
        "sem_db_009",
        "Redis is an in-memory key-value data structure store utilized as a cache, message broker, and fast database. Because all data resides in RAM, Redis achieves sub-millisecond read and write latencies. Redis supports rich data structures including Strings, Lists, Sets, Sorted Sets with score indexing, Hashes, Bitmaps, and HyperLogLogs. Persistence is maintained via periodic Point-in-Time snapshots (RDB) and append-only log files (AOF) with background rewrite capabilities.",
        "Redis in-memory architecture, data structures, and persistence models",
    )

    add(
        "sem_db_010",
        "Database normalization is the systematic process of organizing relational database schemas to minimize data redundancy and prevent insertion, update, and deletion anomalies. First Normal Form (1NF) eliminates repeating groups and enforces atomic attribute values. Second Normal Form (2NF) requires 1NF and ensures all non-key attributes are fully functionally dependent on the primary key. Third Normal Form (3NF) eliminates transitive functional dependencies, ensuring every non-key column depends solely on the primary key.",
        "Database normalization forms (1NF, 2NF, 3NF) and anomaly prevention",
    )

    return samples
