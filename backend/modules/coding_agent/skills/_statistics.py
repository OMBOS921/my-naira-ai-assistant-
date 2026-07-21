"""
SkillStatistics — aggregated metrics across the entire skills subsystem.

Tracks requests, latency, routing decisions, and per-skill statistics.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from backend.modules.coding_agent.skills._types import SkillStatistics


@dataclass
class AggregatedStatistics:
    """Aggregated metrics across all skills."""

    total_requests: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    total_latency_ms: float = 0.0
    average_latency_ms: float = 0.0
    routing_count: int = 0
    composition_count: int = 0
    per_skill: dict[str, SkillStatistics] = field(default_factory=dict)
    start_time: float = field(default_factory=time.time)

    def record_skill(
        self, skill_name: str, duration_ms: float, success: bool
    ) -> None:
        self.total_requests += 1
        self.total_latency_ms += duration_ms
        if success:
            self.successful_executions += 1
        else:
            self.failed_executions += 1
        if self.total_requests > 0:
            self.average_latency_ms = self.total_latency_ms / self.total_requests

        stats = self.per_skill.setdefault(
            skill_name, SkillStatistics()
        )
        stats.record(duration_ms, success)

    def record_routing(self) -> None:
        self.routing_count += 1

    def record_composition(self) -> None:
        self.composition_count += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "total_latency_ms": round(self.total_latency_ms, 2),
            "average_latency_ms": round(self.average_latency_ms, 2),
            "routing_count": self.routing_count,
            "composition_count": self.composition_count,
            "per_skill": {
                name: {
                    "total_requests": s.total_requests,
                    "successful_executions": s.successful_executions,
                    "failed_executions": s.failed_executions,
                    "average_latency_ms": round(s.average_latency_ms, 2),
                    "last_error": s.last_error,
                }
                for name, s in self.per_skill.items()
            },
            "uptime_seconds": round(time.time() - self.start_time, 2),
        }
