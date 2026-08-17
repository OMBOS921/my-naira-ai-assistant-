"""
Technical Encyclopedia Domain Generator for Dataset A.
Generates comprehensive deep engineering expository articles across computer science and systems.
"""

from __future__ import annotations

from typing import Any


def get_technical_encyclopedia_samples() -> list[dict[str, Any]]:
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
                "notes": notes or "Technical encyclopedia deep architectural exposition",
            },
        })

    add(
        "sem_enc_001",
        "operating_systems",
        "Understanding how Linux manages physical memory requires studying the Buddy Allocator and Slab Allocator subsystems. The Buddy Allocator manages physical memory page frames (typically 4 KB each) by grouping contiguous frames into power-of-two blocks (order 0 up to order 11, spanning 4 KB to 4 MB). When a sub-page kernel object (such as an inode, dentry, or socket buffer) requires memory, allocating a full 4 KB page would cause severe internal memory fragmentation. To solve this, the Slab Allocator (SLUB) carves full pages obtained from the buddy system into caches of fixed-size object slabs, eliminating allocation overhead and keeping frequently used data structures pre-initialized in CPU L1/L2 caches.",
        "Linux physical memory management: Buddy system and SLUB allocator",
    )

    add(
        "sem_enc_002",
        "computer_architecture",
        "Cache line false sharing is a subtle and debilitating performance degradation anomaly in symmetric multiprocessing (SMP) multithreaded software. Modern microprocessors maintain cache coherence at the granularity of a Cache Line (typically 64 contiguous bytes in x86-64 and ARM64 architectures) rather than individual byte addresses. When two threads executing on separate CPU cores concurrently modify independent variables that happen to reside within the same 64-byte cache line, the underlying hardware MESI protocol repeatedly invalidates and transfers the entire cache line between core caches (cache line bouncing), inducing severe pipeline stalls. Software engineers resolve false sharing by aligning variables to 64-byte boundaries using `alignas(64)` in C++ or adding explicit cache-line padding fields.",
        "Cache line false sharing, 64-byte alignment, and MESI bouncing",
    )

    add(
        "sem_enc_003",
        "networking",
        "The Domain Name System Security Extensions (DNSSEC) strengthen DNS infrastructure against cache poisoning, spoofing, and man-in-the-middle attacks by introducing cryptographic authentication to DNS records. DNSSEC does not encrypt DNS queries for confidentiality, but rather signs Resource Record Sets (RRsets) using public-key cryptography. A DNS zone contains Resource Record Signatures (RRSIG), DNSKEY public keys, and Delegation Signer (DS) hashes. A validating DNS resolver verifies the chain of trust starting from the globally trusted root zone anchor down through TLD servers to the authoritative child domain, guaranteeing data origin authenticity and integrity.",
        "DNSSEC cryptographic chain of trust and RRSIG validation",
    )

    add(
        "sem_enc_004",
        "databases",
        "Log-Structured Merge-Trees (LSM-Trees) maintain efficient read performance in write-heavy storage engines via Bloom filters and multi-level Leveled Compaction. Because an LSM-tree distributes key versions across multiple SSTable files on disk, querying a non-existent key could theoretically require scanning every SSTable from disk (read amplification). To prevent unnecessary disk seeks, every SSTable header stores a compact in-memory Bloom filter. If the Bloom filter returns false, the storage engine skips the file with zero disk I/O. During background compaction, older SSTables from level L are merged into level L+1, purging deleted tombstones and deduplicating historical key updates.",
        "LSM-Tree read amplification mitigations, Bloom filters, and Leveled Compaction",
    )

    add(
        "sem_enc_005",
        "security",
        "Server-Side Request Forgery (SSRF) is a critical web security vulnerability wherein an attacker coerces a vulnerable backend server into sending unauthorized HTTP or TCP requests to internal or external systems. In cloud environments (such as AWS, Google Cloud, and Azure), SSRF vulnerabilities are frequently exploited to query internal cloud instance metadata services (e.g., `http://169.254.169.254/latest/meta-data/`) to steal temporary IAM role credentials and security tokens. Comprehensive defenses against SSRF include enforcing strict destination domain whitelists, disallowing private IP address ranges (RFC 1918), disabling HTTP redirects in backend HTTP client libraries, and requiring IMDSv2 session token headers in cloud deployments.",
        "Server-Side Request Forgery (SSRF) cloud metadata exploitation and IMDSv2 defense",
    )

    add(
        "sem_enc_006",
        "programming",
        "Abstract Syntax Trees (AST) represent the hierarchical syntactic structure of source code as parsed by a compiler or interpreter. In an AST, interior nodes represent language operators, control statements (e.g., `IfStatement`, `ForLoop`, `FunctionDeclaration`), and expressions, while leaf nodes represent operands, literal constants, and variable identifiers. Linters, static analyzers, and code formatters (such as ESLint, Prettier, and Python AST modules) traverse the AST using the Visitor design pattern to inspect coding conventions, identify security vulnerabilities, and perform automated code transformations without executing source text.",
        "Abstract Syntax Tree (AST) structure, Visitor pattern, and static analysis",
    )

    add(
        "sem_enc_007",
        "software_engineering",
        "The Circuit Breaker pattern prevents cascading failures in distributed microservices architectures when downstream dependencies experience transient outages or high latency. Modeled after electrical circuit breakers, the software breaker resides in one of three operational states: Closed (requests flow normally to downstream services; failures are tracked against an error threshold), Open (the failure threshold was exceeded; all incoming requests fail immediately without invoking the downstream service, returning cached fallbacks and protecting the downstream system from overload), and Half-Open (after a timeout duration, a limited number of probe requests are allowed through; if they succeed, the breaker resets to Closed; if they fail, it trips back to Open).",
        "Circuit Breaker pattern states (Closed, Open, Half-Open) in microservices",
    )

    add(
        "sem_enc_008",
        "web_development",
        "The Critical Rendering Path is the sequence of browser operations that converts HTML, CSS, and JavaScript into active screen pixels on the initial page load. Optimizing the Critical Rendering Path minimizes the Time to First Contentful Paint (FCP) and Largest Contentful Paint (LCP). Key optimization strategies include: minifying and inlining critical CSS above the fold while loading non-critical stylesheets asynchronously; deferring non-essential JavaScript execution using `async` or `defer` script attributes to prevent DOM parsing parser blocking; and implementing responsive image preloading via `<link rel='preload'>` tags.",
        "Critical Rendering Path optimization and Core Web Vitals (FCP, LCP)",
    )

    return samples
