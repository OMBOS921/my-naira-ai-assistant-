"""
SkillHealth — health reporting for the skills subsystem.

Provides health checks for individual skills and the subsystem as a whole.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from backend.modules.coding_agent.skills._types import SkillHealthReport


@dataclass
class SkillHealthReportBuilder:
    """Builds health reports for the entire skill subsystem."""

    @staticmethod
    def subsystem_report(
        registered_skills: list[str],
        active_skills: list[str],
        degraded: bool,
        stats: Any,
    ) -> dict[str, Any]:
        return {
            "subsystem": "skills",
            "healthy": not degraded and len(active_skills) > 0,
            "degraded": degraded,
            "registered_skills_count": len(registered_skills),
            "active_skills_count": len(active_skills),
            "registered_skills": registered_skills,
            "active_skills": active_skills,
            "statistics": stats.to_dict() if stats else {},
            "timestamp": time.time(),
        }

    @staticmethod
    def skill_report(
        name: str,
        is_registered: bool,
        is_active: bool,
        healthy: bool,
        details: dict[str, Any] | None = None,
    ) -> SkillHealthReport:
        if healthy and is_registered and is_active:
            return SkillHealthReport.healthy(
                name, **(details or {})
            )
        reason = "unhealthy"
        if not is_registered:
            reason = "not_registered"
        elif not is_active:
            reason = "inactive"
        return SkillHealthReport.unhealthy(
            name, reason=reason, **(details or {})
        )
