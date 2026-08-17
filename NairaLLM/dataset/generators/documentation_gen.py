"""
Technical Documentation & Architecture Guides Domain Generator for Dataset A.
Generates comprehensive technical prose on Architecture Decision Records (ADRs), post-mortem root-cause analyses, SemVer, and runbooks.
"""

from __future__ import annotations

from typing import Any


def get_documentation_samples() -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []

    def add(sample_id: str, text: str, notes: str = "") -> None:
        samples.append({
            "id": sample_id,
            "domain": "documentation",
            "language": "en",
            "text": text.strip(),
            "provenance": {
                "provenance_id": f"prov_{sample_id}",
                "author": "nairallm_semantic_curator",
                "license": "Apache-2.0",
                "acquisition_method": "controlled_synthetic",
                "notes": notes or "Technical documentation, ADRs, post-mortems, and engineering guides",
            },
        })

    add(
        "sem_doc_003",
        "Architecture Decision Records (ADRs) capture significant architectural choices made along with their context and consequences. A standard ADR follows the Michael Nygard format containing five essential sections: Title (short noun phrase), Status (Proposed, Accepted, Deprecated, Superseded), Context (the technical or business problem, constraints, and evaluated options), Decision (the affirmative architectural path chosen), and Consequences (the resulting trade-offs, positive benefits, and liabilities introduced to the system). Storing ADRs in git ensures architectural rationale is preserved alongside source code.",
        "Architecture Decision Records (ADR) structure and Nygard format",
    )

    add(
        "sem_doc_004",
        "Blameless Post-Mortem incident reports are essential for fostering a resilient engineering culture of continuous learning. Following a production outage, the incident response team conducts a systematic review structured around: Incident Summary (time of detection, severity, customer impact), Detailed Timeline (minute-by-minute progression of alerts, diagnostic attempts, and mitigations), Root Cause Analysis (utilizing the '5 Whys' technique to identify systemic and procedural vulnerabilities rather than attributing fault to individual engineers), and Action Items (prioritized, assigned engineering fixes to prevent recurrence).",
        "Blameless post-mortem incident report structure and 5 Whys analysis",
    )

    add(
        "sem_doc_005",
        "Semantic Versioning 2.0.0 (SemVer) establishes a formal version numbering standard of `MAJOR.MINOR.PATCH` with optional pre-release labels. Increment the MAJOR version when you introduce incompatible API breaking changes; increment the MINOR version when you add functionality in a backward-compatible manner; and increment the PATCH version when you make backward-compatible bug fixes. Adhering to SemVer allows automated package managers (npm, pip, cargo) to safely resolve dependency ranges (`^1.2.0` or `~1.2.0`) without risking silent runtime breakage.",
        "Semantic Versioning 2.0.0 specification rules (MAJOR.MINOR.PATCH)",
    )

    add(
        "sem_doc_006",
        "Operational Runbooks (Playbooks) provide step-by-step procedures for on-call engineers to diagnose, mitigate, and resolve production alerts. An effective runbook declares: Alert Name, Severity Level, Business Impact Description, Initial Triage Commands (inspecting logs, checking CPU/memory, verifying database connection pool health), Remediation Procedures (scaling pod replicas, failing over to replica databases, restarting hung daemons), and Escalation Contacts with SLA timelines, drastically reducing Mean Time to Resolution (MTTR).",
        "Operational runbook documentation design and MTTR reduction",
    )

    add(
        "sem_doc_007",
        "The 'Keep a Changelog' standard provides human-readable release notes documenting notable changes for each version of a project. Changes are categorized under standard verbs: `Added` (new features), `Changed` (changes in existing functionality), `Deprecated` (soon-to-be-removed features), `Removed` (now removed features), `Fixed` (any bug fixes), and `Security` (in vulnerabilities addressed). Maintaining chronological, categorized changelogs improves communication between library maintainers and consuming developers.",
        "Keep a Changelog release notes standard and categorization taxonomy",
    )

    return samples
