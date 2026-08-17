"""
Naira OS Architectural Concepts Domain Generator for Dataset A.
Generates comprehensive technical prose on Naira OS modular subsystems, Fast Command Router, Action Engine, and Bounded Autonomy.
"""

from __future__ import annotations

from typing import Any


def get_naira_architecture_samples() -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []

    def add(sample_id: str, text: str, notes: str = "") -> None:
        samples.append({
            "id": sample_id,
            "domain": "naira_architecture",
            "language": "en",
            "text": text.strip(),
            "provenance": {
                "provenance_id": f"prov_{sample_id}",
                "author": "nairallm_semantic_curator",
                "license": "Apache-2.0",
                "acquisition_method": "controlled_synthetic",
                "notes": notes or "Naira OS core subsystem and bounded autonomy architectural overview",
            },
        })

    add(
        "sem_naira_004",
        "The Fast Command Router (FCR) is the deterministic low-latency triage gateway of Naira OS. When an inbound user request arrives, the FCR executes regex matching, semantic classification, and intent extraction before invoking the heavier neural LLM runtime. For standard system operations (such as volume control, opening applications, or querying battery percentages), the FCR bypasses model inference entirely, achieving sub-10ms response latencies while conserving host CPU and battery power.",
        "Naira OS Fast Command Router (FCR) deterministic triage architecture",
    )

    add(
        "sem_naira_005",
        "The Action Engine in Naira OS serves as the execution coordinator that translates structured tool calls into concrete operating system system calls and API invocations. Operating behind a strict capability-based security model, the Action Engine validates all parameter types against JSON schemas, verifies file system path boundaries, enforces timeout deadlines, and captures stdout/stderr telemetry into the session execution log.",
        "Naira OS Action Engine execution coordinator and capability sandbox",
    )

    add(
        "sem_naira_006",
        "The Naira Memory Subsystem orchestrates a tiered persistence architecture consisting of Short-Term Working Memory (in-memory context windows), Session Memory (conversational history databases), and Long-Term Semantic Memory (vector index database). Key facts, user preferences, and project relationships are automatically summarized, embedded, and indexed with hybrid keyword-vector search for contextual recall across reboots.",
        "Naira OS Memory Subsystem tiered architecture and hybrid retrieval",
    )

    add(
        "sem_naira_007",
        "The Internal EventBus in Naira OS implements a publish-subscribe event-driven architecture that decouples independent subsystems. Core modules—including Browser Automation, Coding Agent, Vision Module, and Voice Pipeline—communicate by publishing typed event objects (such as `ToolExecutionStarted`, `FileModifiedEvent`, `SafetyGateTriggered`). The EventBus guarantees asynchronous non-blocking event distribution and structured audit logging.",
        "Naira OS Internal EventBus pub-sub decoupled communication model",
    )

    return samples
