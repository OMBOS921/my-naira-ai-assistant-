"""
Domain Deep Dives Generator for Dataset A.
Generates comprehensive multi-domain technical narratives across databases, computer networks, AI architectures, and operating systems.
"""

from __future__ import annotations

from typing import Any


def get_domain_deep_dives_samples() -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []

    def add(sample_id: str, domain: str, lang: str, text: str, notes: str = "") -> None:
        samples.append({
            "id": sample_id,
            "domain": domain,
            "language": lang,
            "text": text.strip(),
            "provenance": {
                "provenance_id": f"prov_{sample_id}",
                "author": "nairallm_semantic_curator",
                "license": "Apache-2.0",
                "acquisition_method": "controlled_synthetic",
                "notes": notes or "Domain deep dive and technical exposition",
            },
        })

    add(
        "sem_dd_001",
        "databases",
        "en",
        "Database Index Skip Scans (Loose Index Scans) optimize composite index lookups when leading index columns have low cardinality (e.g., boolean or enum flags) but are omitted from the WHERE filter predicate. In a composite B-Tree index on `(status, created_at)`, a standard query filtering exclusively on `created_at > '2026-01-01'` would traditionally trigger an expensive full sequential table scan because the leading `status` column is absent from the query. With Index Skip Scan enabled, the query engine queries the B-Tree for each distinct value of `status`, executing targeted logarithmic sub-range scans for each value and concatenating results with minimal disk I/O.",
        "Database Index Skip Scans on composite B-Trees with low leading cardinality",
    )

    add(
        "sem_dd_002",
        "operating_systems",
        "en",
        "Linux kernel HugePages reduce memory address translation overhead for memory-intensive applications like database servers, JVM runtimes, and large language model inference engines. On x86-64 architectures, standard page sizes are 4 KB. For a process allocating 64 GB of RAM, a 4 KB page model requires 16 million page table entries, causing severe Translation Lookaside Buffer (TLB) thrashing and high TLB miss rates. Transparent HugePages (THP) and static HugePages allocate memory in 2 MB or 1 GB blocks, reducing page table footprint by a factor of 512x and drastically improving memory access latency.",
        "Linux kernel HugePages (2MB, 1GB) and TLB miss reduction",
    )

    add(
        "sem_dd_003",
        "networking",
        "en",
        "Software-Defined Networking (SDN) fundamentally decouples the Network Control Plane (the brain deciding where traffic is routed) from the Data Forwarding Plane (the underlying hardware switches forwarding packets). Traditional enterprise routers execute proprietary routing protocols (OSPF, BGP, Spanning Tree) locally on each physical switch. In an SDN architecture utilizing the OpenFlow protocol, centralized software controllers maintain a global view of the entire network topology, dynamically programming flow tables in programmable hardware switches to implement agile traffic engineering and network virtualization.",
        "Software-Defined Networking (SDN), Control Plane decoupling, and OpenFlow",
    )

    add(
        "sem_dd_004",
        "computer_architecture",
        "en",
        "Cache oblivious algorithms are algorithmic techniques designed to exploit CPU cache hierarchies efficiently without tuning algorithm parameters (such as block size or cache line length) for specific hardware platforms. By utilizing recursive divide-and-conquer decompositions, cache-oblivious matrix multiplication and cache-oblivious Funnelsort automatically achieve optimal cache complexity across all levels of the memory hierarchy (L1, L2, L3, and main RAM) simultaneously, maximizing spatial and temporal locality on any CPU architecture.",
        "Cache-oblivious algorithms and recursive memory locality optimization",
    )

    add(
        "sem_dd_005",
        "hindi_linguistics",
        "hi",
        "प्राकृतिक भाषा प्रसंस्करण में 'सिमेंटिक समानता' (Semantic Similarity) दो शब्दों, वाक्यों या पाठ अनुच्छेदों के बीच अर्थ की निकटता को मापती है। जब शब्दों को 'वर्ड एम्बेडिंग' (Word Embeddings - जैसे Word2Vec, GloVe या ट्रांसफ़ॉर्मर एम्बेडिंग्स) के माध्यम से बहु-आयामी सघन वेक्टर स्पेस में मैप किया जाता है, तो कोसाइन समानता (Cosine Similarity) का उपयोग करके उनके बीच के कोण की गणना की जाती है। उदाहरण के लिए, हिंदी में 'जल', 'पानी' और 'नीर' के वेक्टर एक-दूसरे के अत्यधिक निकट स्थित होते हैं, जिससे सर्च इंजन और भाषा मॉडल समानार्थी शब्दों को सटीकता से पहचान पाते हैं।",
        "Semantic similarity, vector embeddings and cosine similarity in Hindi",
    )

    add(
        "sem_dd_006",
        "hinglish_discourse",
        "hinglish",
        "Production backend systems me graceful shutdown implement karna zero-downtime rolling updates ke liye mandatory hota hai. Jab Kubernetes pod ko `SIGTERM` signal send karta hai, toh application ko immediately process exit nahi karna chahiye. Pehle HTTP listener naye incoming connections accept karna band karta hai, current in-flight requests ko complete hone ke liye 15-30 seconds ka grace period allow karta hai, database connection pools aur Kafka consumers ko cleanly close karta hai, aur phir `process.exit(0)` trigger karta hai.",
        "Graceful shutdown and SIGTERM signal handling in Hinglish",
    )

    add(
        "sem_dd_007",
        "software_engineering",
        "en",
        "Database Connection Leaks are insidious resource starvation defects in backend services caused when application threads acquire a database connection from a connection pool (such as HikariCP or SQLAlchemy) but fail to release or close the connection back to the pool under error or exception conditions. Over time, the pool exhausts its maximum allowed active connections, causing all subsequent incoming user requests to block indefinitely or fail with connection acquisition timeout errors. Defenses include using language-managed scoping constructs (Python `with` context managers, Java `try-with-resources`, Go `defer`) and configuring pool leak-detection thresholds.",
        "Database connection leaks, resource starvation, and context manager defenses",
    )

    add(
        "sem_dd_008",
        "security",
        "en",
        "Timing Attacks are cryptographic side-channel attacks wherein an adversary analyzes the exact elapsed execution time of cryptographic operations or string comparisons to infer secret keys or passwords. For example, standard string equality comparisons (`str1 == str2`) return `false` immediately upon encountering the first non-matching character (early exit optimization), leaking the length of matching prefix characters. To prevent timing side-channels, cryptographic libraries enforce Constant-Time Comparison functions (such as `crypto.timingSafeEqual` in Node.js or `hmac.compare_digest` in Python) that always inspect every byte regardless of mismatch locations.",
        "Timing side-channel attacks and constant-time string comparisons",
    )

    return samples
