"""
Applied Software Engineering & Systems Architecture Domain Generator for Dataset A.
Generates comprehensive technical prose on Linux io_uring, PostgreSQL JSONB indexing, Prometheus observability, and Event Sourcing.
"""

from __future__ import annotations

from typing import Any


def get_applied_engineering_samples() -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []

    def add(sample_id: str, domain: str, text: str, notes: str = "") -> None:
        samples.append({
            "id": sample_id,
            "domain": domain,
            "language": "en",
            "text": text.strip(),
            "provenance": {
                "provenance_id": f"prov_{sample_id}",
                "author": "nairallm_semantic_curator",
                "license": "Apache-2.0",
                "acquisition_method": "controlled_synthetic",
                "notes": notes or "Applied software engineering and systems architecture exposition",
            },
        })

    add(
        "sem_eng_001",
        "operating_systems",
        "Linux io_uring is a revolutionary asynchronous I/O interface that completely reimagines system call mechanics for ultra-high-throughput disk and network operations. Traditional asynchronous interfaces like POSIX aio and epoll require repeated context switching into the kernel via system calls for submission and completion. In contrast, io_uring establishes two lockless ring buffers shared directly in memory between user space and kernel space: the Submission Queue (SQ) and the Completion Queue (CQ). An application enqueues multiple I/O requests into the SQ ring buffer and, in SQPOLL mode with a dedicated kernel polling thread, executes millions of I/O operations per second with zero system call overhead.",
        "Linux io_uring shared ring buffer architecture and SQPOLL mode",
    )

    add(
        "sem_eng_002",
        "databases",
        "PostgreSQL Generalized Inverted Index (GIN) and Block Range Index (BRIN) structures provide specialized indexing tailored for semi-structured and time-series data. GIN indexes are designed for composite data types containing multiple elements, such as full-text search document vectors (`tsvector`) and binary JSON documents (`jsonb`). A GIN index maps each individual internal key or token to a posting list of matching table row locations, enabling sub-millisecond JSON attribute filtering (`@>` operator). Conversely, BRIN indexes summarize minimum and maximum column values for contiguous disk page ranges (e.g., 128 pages), occupying a fraction of 1% of the storage space of B-Trees, ideal for physically sorted append-only time-series tables.",
        "PostgreSQL GIN indexing for JSONB and BRIN for time-series data",
    )

    add(
        "sem_eng_003",
        "software_engineering",
        "Event Sourcing and Command Query Responsibility Segregation (CQRS) represent powerful complementary architectural patterns for complex business domains. In traditional CRUD architectures, the database stores only the current state of an entity, discarding the historical sequence of mutations. In Event Sourcing, every state change is captured immutably as a domain event (e.g., `OrderPlaced`, `PaymentReceived`, `ItemShipped`) in an append-only Event Store. CQRS separates the write model (which validates business commands and produces events) from read projections (which asynchronously consume events to build highly denormalized, read-optimized query views in Elasticsearch or Redis).",
        "Event Sourcing and CQRS architecture and event store projections",
    )

    add(
        "sem_eng_004",
        "software_engineering",
        "The Transactional Outbox Pattern solves the dual-write problem in distributed event-driven microservices. When a microservice must update its local database and publish a corresponding event to an external message broker (like Apache Kafka or RabbitMQ), executing both operations independently can cause severe inconsistencies if the application crashes or network fails between the two steps. In the Outbox pattern, the service saves the business entity and inserts the outbound event into a dedicated `outbox` table within the same atomic local ACID database transaction. A background Change Data Capture (CDC) process (using Debezium or transaction log tailing) reliably reads the outbox table and streams events to the message broker with guaranteed at-least-once delivery.",
        "Transactional Outbox Pattern and CDC log tailing for microservices",
    )

    add(
        "sem_eng_005",
        "software_engineering",
        "Modern systems observability relies on the three pillars: Metrics, Logs, and Traces. Prometheus collects numerical time-series metrics via a pull-based HTTP scraping model. Prometheus defines four core metric types: Counter (a monotonically increasing cumulative metric, e.g., total HTTP requests), Gauge (a single numerical value that can arbitrarily fluctuate up or down, e.g., current memory utilization or concurrent active connections), Histogram (samples observations into configurable buckets and counts occurrences, enabling accurate percentile P90/P99 latency calculations), and Summary (calculates configurable quantiles over a sliding time window on the client side).",
        "Prometheus metric types (Counter, Gauge, Histogram, Summary) and observability",
    )

    add(
        "sem_eng_006",
        "security",
        "HTTP Strict Transport Security (HSTS) and Subresource Integrity (SRI) protect web applications from network downgrade and content tampering attacks. The HSTS response header (`Strict-Transport-Security: max-age=63072000; includeSubDomains; preload`) instructs web browsers to automatically upgrade all future HTTP requests to HTTPS and strictly reject connections with invalid, expired, or self-signed TLS certificates, preventing SSL Stripping man-in-the-middle attacks. Subresource Integrity (SRI) allows browsers to verify that resources fetched from third-party Content Delivery Networks (CDNs, such as JavaScript libraries) have not been maliciously modified by validating their cryptographic base64 SHA-384 hashes.",
        "HSTS security headers and Subresource Integrity (SRI) CDN validation",
    )

    add(
        "sem_eng_007",
        "networking",
        "Low-level Linux TCP socket configuration parameters directly dictate high-concurrency network server performance. The `SO_REUSEPORT` socket option allows multiple independent server processes or threads to bind to the identical IP address and TCP port; the Linux kernel automatically load-balances incoming connection requests across the listening sockets at the kernel level, eliminating accept mutex contention. Disabling Nagle's algorithm via the `TCP_NODELAY` socket flag forces the kernel to transmit packets immediately rather than buffering small payloads, eliminating 40ms delayed-ACK latencies in interactive RPC microservices.",
        "Linux TCP socket tuning (SO_REUSEPORT, TCP_NODELAY, Nagle algorithm)",
    )

    add(
        "sem_eng_008",
        "programming",
        "Virtual Machine (VM) execution models are primarily categorized into Stack-Based and Register-Based architectures. In a Stack-Based VM (such as the Java Virtual Machine and Python's CPython interpreter), instructions implicitly operate on an evaluation operand stack (e.g., PUSH, ADD, POP), resulting in compact, simple variable-length bytecode instruction formats. In contrast, a Register-Based VM (such as the LuaJIT VM and Android Dalvik/ART VM) explicitly specifies source and destination virtual registers in instruction operands (e.g., `ADD r1, r2, r3`), resulting in fewer total instructions executed per loop and easier translation to underlying physical CPU registers.",
        "Stack-based vs Register-based bytecode virtual machines (JVM vs LuaJIT)",
    )

    return samples
