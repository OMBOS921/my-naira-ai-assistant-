"""
Expanded Hinglish Technical Discourse Domain Generator for Dataset A.
Generates comprehensive developer discussions covering backend systems, database migrations, security, and cloud scalability.
"""

from __future__ import annotations

from typing import Any


def get_hinglish_expanded_samples() -> list[dict[str, Any]]:
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
                "notes": notes or "Expanded Hinglish technical discourse and backend design",
            },
        })

    add(
        "sem_hing_021",
        "Zero-downtime database schema migrations execute karte waqt backwards compatibility maintain karna sabse critical rule hota hai. Kabhi bhi ek single migration step me live column ka name change ya delete mat karo. Pehle naya column add karo, application code ko update karke dono old aur new columns me dual-write enable karo, background worker ke through historical data backfill karo, aur jab saare read queries new column pe point karne lagein tab final cleanup PR me purana column drop karo.",
        "Zero-downtime database schema migrations pattern in Hinglish",
    )

    add(
        "sem_hing_022",
        "Microservices me distributed transactions handle karne ke liye 2-Phase Commit (2PC) ki jagah Saga pattern prefer kiya jata hai. 2PC me database locks across network hold hote hain jo high latency aur single-point-of-failure create karte hain. Saga pattern me har microservice apna local ACID transaction execute karti hai aur event publish karti hai. Agar downstream step fail ho jaye, toh orchestrator compensating transactions trigger karta hai jo previous actions ko revert karte hain.",
        "Saga pattern vs Two-Phase Commit in Hinglish",
    )

    add(
        "sem_hing_023",
        "High-performance caching layer design karte time Cache-Aside (Lazy Loading) aur Write-Through strategies ke trade-offs analyze karne chahiye. Cache-Aside me application pehle cache check karti hai, cache miss hone pe database se fetch karke cache populate karti hai. Isme data stale hone ka risk rehta hai, isliye appropriate TTL (Time To Live) set karna aur database update hone par cache keys explicitly invalidate karna mandatory hota hai.",
        "Redis Cache-Aside vs Write-Through strategies in Hinglish",
    )

    add(
        "sem_hing_024",
        "Frontend applications me Single Page Application (SPA) vs Server-Side Rendering (SSR) ka decision Search Engine Optimization (SEO) aur Initial Page Load requirements pe depend karta hai. Pure client-side React SPA me initial HTML empty hota hai aur JS bundle download hone ke baad DOM render hota hai. Next.js jaisa SSR framework server pe hi dynamic HTML render karke stream karta hai, jisse First Contentful Paint (FCP) fast hota hai aur web crawlers content easily index kar paate hain.",
        "SPA vs SSR architectural trade-offs in Hinglish",
    )

    add(
        "sem_hing_025",
        "Kubernetes ingress controllers me Nginx ya Traefik use karke SSL/TLS termination aur path-based routing manage ki jaati hai. External HTTPS traffic ingress layer pe decrypt hota hai aur internal cluster network me plain HTTP ke through backend pods me forward hota hai. Agar high security compliance required ho toh service mesh (jaise Istio ya Linkerd) configure karke pod-to-pod mTLS encryption enforce kiya jata hai.",
        "Kubernetes ingress controllers and mTLS service mesh in Hinglish",
    )

    add(
        "sem_hing_026",
        "Python me memory profiling karte time `tracemalloc` aur `objgraph` libraries use karke memory leaks detect kiye jaate hain. Jab kisi circular reference me `__del__` destructor method define hota hai, toh Python ka garbage collector un cycles ko collect nahi kar pata aur memory leak hoti hai. Weak references (`weakref` module) use karke objects ke cyclic relationships ko safely break kiya ja sakta hai.",
        "Python memory leak profiling and circular reference resolution in Hinglish",
    )

    add(
        "sem_hing_027",
        "System reliability engineering me SRE teams teen core metrics define karti hain: Service Level Indicators (SLI), Service Level Objectives (SLO), aur Service Level Agreements (SLA). SLI actual measured performance metric hoti hai (e.g. 99.9% requests respond within 200ms). SLO internal target threshold hoti hai, aur SLA legal contractual agreement hota hai jiske breach hone pe financial penalties lagti hain. Error budgets SREs ko feature velocity aur stability ke beech balance maintain karne me help karte hain.",
        "SRE core metrics (SLI, SLO, SLA, Error Budgets) in Hinglish",
    )

    add(
        "sem_hing_028",
        "API authentication me OAuth 2.0 PKCE (Proof Key for Code Exchange) flow Single Page Apps aur mobile apps ke liye standard hai. Client-side code me client secret store karna insecure hota hai kyunki koi bhi user browser inspect karke secret extract kar sakta hai. PKCE dynamically code verifier generate karta hai aur uska SHA-256 hash (code challenge) auth server ko bhejta hai, jisse authorization code interception attacks permanently eliminate ho jaate hain.",
        "OAuth 2.0 PKCE flow for mobile and SPAs in Hinglish",
    )

    add(
        "sem_hing_029",
        "PostgreSQL me high-volume write operations optimize karte time `UNLOGGED` tables aur batch `COPY` command use karna standard practice hai. Regular `INSERT` queries har row pe WAL logs generate karti hain jo disk I/O bottleneck banti hain. Batch processing ke liye `COPY table_name FROM STDIN WITH (FORMAT csv)` bulk insert stream use karne se 10x-50x throughput gain milta hai.",
        "PostgreSQL bulk data ingestion with COPY command in Hinglish",
    )

    add(
        "sem_hing_030",
        "Modern CI/CD pipelines me immutable infrastructure paradigm follow kiya jata hai. Jab bhi naya software release deploy hota hai, existing running servers ko in-place modify karne ke bajay naye pristine virtual machines ya container pods spin up kiye jaate hain aur traffic transition ke baad purane instances terminate kar diye jaate hain. Isse configuration drift aur environment inconsistency bugs zero ho jaate hain.",
        "Immutable infrastructure and blue-green container deployments in Hinglish",
    )

    return samples
