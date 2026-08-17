"""
Advanced Hinglish Engineering & Career Discourse Domain Generator for Dataset A.
Generates comprehensive developer discussions covering system design interviews, career engineering, tech lead decisions, and cloud cost optimization.
"""

from __future__ import annotations

from typing import Any


def get_hinglish_advanced_samples() -> list[dict[str, Any]]:
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
                "notes": notes or "Advanced Hinglish developer strategy and system design discourse",
            },
        })

    add(
        "sem_hing_031",
        "System design interviews me URL shortener service design karte time high-level architecture aur database schema clear hona chahiye. Base62 encoding use karke 64-bit auto-increment ID ya distributed Snowflake ID ko 7-character string me encode kiya ja sakta hai. 100:1 read-to-write ratio hota hai, isliye aggressive Redis caching use karke 80% read traffic cache se serve karna chahiye aur consistent hashing ke saath multi-region database replication deploy karna padega.",
        "System design URL shortener architecture in Hinglish",
    )

    add(
        "sem_hing_032",
        "Cloud infrastructure cost optimize karte time AWS compute savings plans, Spot instances, aur S3 lifecycle policies implement karna huge savings deta hai. Non-critical background worker jobs (jaise video encoding, report generation) ko Spot instances pe run karo jo 70-90% cheaper hoti hain. S3 me data access patterns monitor karke 30 din purane logs ko automatically Glacier Flexible Retrieval tier me transition karo.",
        "AWS cloud cost optimization and FinOps best practices in Hinglish",
    )

    add(
        "sem_hing_033",
        "Go programming language me concurrency model Communicating Sequential Processes (CSP) theory pe based hai. Go me 'do not communicate by sharing memory; instead, share memory by communicating'. Goroutines lightweight green threads hoti hain jo initial 2KB stack size se start hoti hain. Goroutines ke beech data safe transmission ke liye buffered aur unbuffered channels use kiye jaate hain, aur `select` statement multiple channel operations ko multiplex karta hai bina lock contention ke.",
        "Go concurrency model (Goroutines, Channels, CSP) in Hinglish",
    )

    add(
        "sem_hing_034",
        "Senior Software Engineer role me transition karte time code likhne ke saath-saath technical debt manage karna aur junior engineers ko mentor karna key responsibility hoti hai. Architecture Decision Records (ADRs) document karke decisions ka context preserve karo, code reviews me constructive feedback do, aur team velocity improve karne ke liye developer tooling aur CI/CD pipelines automate karo.",
        "Senior engineering leadership and mentoring in Hinglish",
    )

    add(
        "sem_hing_035",
        "Elasticsearch me index lifecycle management (ILM) configure karke Hot-Warm-Cold architecture implement ki jaati hai. Hot nodes high-performance NVMe SSDs use karte hain recent active logs ingest karne ke liye. Jab index 7 din purana ho jata hai, toh ILM rule use Warm nodes pe move karta hai jahan data read-only ban jata hai aur replica count reduce ho jata hai. 30 din baad Cold tier me move karke snapshots S3 me archive kiye jaate hain.",
        "Elasticsearch Hot-Warm-Cold ILM cluster architecture in Hinglish",
    )

    add(
        "sem_hing_036",
        "Mobile app performance optimize karte time Network Payload Compression (Brotli/Gzip) aur Image Format modernizations (WebP/AVIF) mandatory hote hain. Heavy JSON parsing mobile main UI thread ko block karke frame drops (jank) cause karti hai, isliye background worker isolates me parsing execute karo aur pagination me infinite scroll ke saath cursor-based pagination use karo taaki duplicate items render na hon.",
        "Mobile client performance and frame rate optimization in Hinglish",
    )

    add(
        "sem_hing_037",
        "Cybersecurity me Content Security Policy (CSP) HTTP headers modern web applications ko XSS attacks se protect karne ka most effective defense mechanism hai. CSP `default-src 'self'` policy define karke unauthorized external domains se JavaScript scripts, styles, aur iframes load hone se block karta hai. Strict nonces use karke inline script execution allow ki ja sakti hai bina `'unsafe-inline'` directive enable kiye.",
        "Content Security Policy (CSP) and nonce protection in Hinglish",
    )

    add(
        "sem_hing_038",
        "Full-stack web applications me WebSockets aur Server-Sent Events (SSE) choose karte time directional data flow identify karna zaroori hai. Agar dashboard me sirf real-time server updates (jaise stock prices, server CPU metrics, build progress) stream karne hain toh SSE simpler aur lighter hota hai kyunki wo standard HTTP/2 multiplexing aur automatic reconnection support karta hai. Jab bidirectional chat ya multi-player collaboration chahiye tabhi WebSockets use karna chahiye.",
        "SSE vs WebSockets architecture comparison in Hinglish",
    )

    return samples
