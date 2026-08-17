"""
Hinglish Technical Discourse Domain Generator for Dataset A.
Generates authentic mixed Hindi-English technical discourse, architecture discussions, and developer debugging narratives.
"""

from __future__ import annotations

from typing import Any


def get_hinglish_discourse_samples() -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []

    def add(sample_id: str, text: str, notes: str = "") -> None:
        samples.append({
            "id": sample_id,
            "domain": "hinglish_discourse",
            "language": "hinglish",
            "text": text.strip(),
            "provenance": {
                "provenance_id": f"prov_{sample_id}",
                "author": "nairallm_semantic_curator",
                "license": "Apache-2.0",
                "acquisition_method": "controlled_synthetic",
                "notes": notes or "Hinglish technical engineering and developer discourse",
            },
        })

    add(
        "sem_hing_005",
        "Production environment me database queries optimize karte time hamesha EXPLAIN ANALYZE run karna chahiye. Agar execution plan me sequential table scan dikh raha hai toh filter columns aur foreign keys pe composite B-Tree indexes add karo. Par dhyan rahe ki excessive indexing se write throughput slow ho sakti hai kyunki har INSERT ya UPDATE operation pe indexes ko bhi rebalance karna padta hai.",
        "Database indexing and query execution plans in Hinglish",
    )

    add(
        "sem_hing_006",
        "Docker containerization me multi-stage builds use karna production images ka size drastically reduce karta hai. Pehle stage me compilers, build tools aur dev dependencies install karke binary compile karo, aur final stage me sirf runtime dependencies aur output artifacts copy karo. Isse final Docker image lightweight rehti hai aur attack surface area bhi minimum ho jata hai.",
        "Docker multi-stage builds and container optimization in Hinglish",
    )

    add(
        "sem_hing_007",
        "Frontend applications me state management architect karte time unnecessary re-renders avoid karna critical hota hai. React me useMemo aur useCallback hooks ka use computationally expensive functions ko memoize karne ke liye kiya jata hai. Lekin har chhoti jagah premature memoization karne se code complexity badhti hai bina noticeable performance gain ke.",
        "Frontend React performance and memoization in Hinglish",
    )

    add(
        "sem_hing_008",
        "High-traffic REST APIs me rate limiting implement karna DDoS attacks aur resource exhaustion se protect karta hai. Redis-based sliding window log ya token bucket algorithm use karke hum per-user aur per-IP request rates enforce kar sakte hain. Jab limit exceed hoti hai toh client ko standard HTTP 429 Too Many Requests status code with Retry-After header return karna chahiye.",
        "API rate limiting algorithms and HTTP 429 in Hinglish",
    )

    add(
        "sem_hing_009",
        "CI/CD automation pipelines me automated testing gatekeeper ki tarah kaam karta hai. Pull Request raise hote hi GitHub Actions workflow unit tests, type checkers (mypy/typescript), aur security linters run karta hai. Jab tak saare checks green pass nahi hote, tab tak main branch me merge block rehna chahiye taaki broken builds production me deploy na hon.",
        "CI/CD pipelines and automated quality gates in Hinglish",
    )

    add(
        "sem_hing_010",
        "Kubernetes cluster me pod autoscaling do tarike se hoti hai: Horizontal Pod Autoscaler (HPA) jo CPU/Memory load ke basis pe pod replicas increase karta hai, aur Vertical Pod Autoscaler (VPA) jo individual container ke resource requests aur limits adjust karta hai. Production workloads ke liye properly tuned readiness aur liveness probes define karna zero-downtime rolling updates ke liye mandatory hai.",
        "Kubernetes pod autoscaling and health probes in Hinglish",
    )

    add(
        "sem_hing_011",
        "Web security me JSON Web Tokens (JWT) authenticate karte time signature verification aur expiration time (exp claim) check karna compulsory hai. JWT secret keys ko hamesha secure environment variables me store karo aur tokens ko local storage ki jagah httpOnly, secure cookies me rakhna chahiye taaki Cross-Site Scripting (XSS) attacks se tokens leak na hon.",
        "JWT authentication and XSS security best practices in Hinglish",
    )

    add(
        "sem_hing_012",
        "Event-driven architecture me Apache Kafka jaise distributed commit logs decoupling provide karte hain. Producers events publish karte hain aur multiple independent consumer groups un events ko apni speed pe process kar sakte hain. Kafka ka partition model horizontal scalability ensure karta hai jabki consumer offset commits at-least-once ya exactly-once processing guarantees dete hain.",
        "Kafka event streaming and consumer offsets in Hinglish",
    )

    add(
        "sem_hing_013",
        "Python backend development me asynchronous concurrency manage karte time asyncio.gather vs asyncio.TaskGroup ke difference ko samajhna zaroori hai. TaskGroup structured concurrency provide karta hai jisme agar koi ek child coroutine exception raise karti hai, toh baki saari sibling tasks automatically cancel ho jaati hain, jisse resource leaks prevent hote hain.",
        "Python asyncio structured concurrency in Hinglish",
    )

    add(
        "sem_hing_014",
        "Microservices me distributed tracing implement karne ke liye OpenTelemetry standard use kiya jata hai. Har incoming request ko ek unique trace ID assign hota hai jo context propagation ke through downstream services me pass hota hai. Jaeger ya Zipkin dashboard pe spans visual karke engineers latency bottlenecks aur cross-service errors ko seconds me locate kar sakte hain.",
        "OpenTelemetry distributed tracing in Hinglish",
    )

    add(
        "sem_hing_015",
        "Git version control me rebase vs merge ka choice team workflow pe depend karta hai. Interactive rebase (git rebase -i) use karke feature branch ki messy commit history ko clean, atomic commits me squash kiya ja sakta hai. Par public shared branches pe force push karna completely avoid karna chahiye taaki teammates ki commit history corrupt na ho.",
        "Git interactive rebase and commit hygiene in Hinglish",
    )

    add(
        "sem_hing_016",
        "Database transactions me Deadlock tab occur hota hai jab do concurrent transactions alag-alag resources pe locks acquire karte hain aur ek-doosre ke lock release hone ka wait karte rehte hain. Deadlocks minimize karne ke liye application code me tables aur rows ko hamesha consistent order me access karna chahiye aur short transaction scopes maintain karne chahiye.",
        "Database deadlocks prevention strategies in Hinglish",
    )

    add(
        "sem_hing_017",
        "Search functionality implement karte time Elasticsearch ya OpenSearch jaise inverted index engines use kiye jaate hain. Inverted index har unique word ko un documents ki list se map karta hai jinme wo word appear hota hai. BM25 scoring algorithm term frequency aur inverse document frequency calculate karke most relevant results top pe rank karta hai.",
        "Inverted index and BM25 search ranking in Hinglish",
    )

    add(
        "sem_hing_018",
        "Mobile backend development me payload optimization ke liye GraphQL ya gRPC better alternatives hote hain traditional REST se. Over-fetching aur under-fetching solve karne ke liye GraphQL client ko exact required fields specify karne deta hai, jisse mobile network bandwidth save hoti hai aur app startup time dramatically fast ho jata hai.",
        "Mobile API payload optimization and GraphQL in Hinglish",
    )

    add(
        "sem_hing_019",
        "Zero Trust network architecture ka core principle hai 'never trust, always verify'. Traditional perimeter-based VPN security ke bajay, har single request ko chahe wo internal network se aaye ya external se, strictly authenticate, authorize aur encrypt kiya jata hai. Mutual TLS (mTLS) microservices ke beech encrypted communication guarantee karta hai.",
        "Zero Trust security architecture and mTLS in Hinglish",
    )

    add(
        "sem_hing_020",
        "Software testing pyramid me broad base unit tests ka hota hai, middle layer integration tests ka, aur top tip End-to-End (E2E) browser tests ka hota hai. E2E tests brittle aur slow hote hain, isliye core business logic ko fast, deterministic unit tests se cover karna chahiye taaki rapid feedback loop maintain rahe.",
        "Testing pyramid and test strategy in Hinglish",
    )

    return samples
