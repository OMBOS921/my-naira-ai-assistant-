"""
SkillConfig — all configuration for the skills subsystem.

No hardcoded values.  Everything is injected via constructor parameters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillConfig:
    """Configuration for the entire skills subsystem.

    All values are configurable.  No hardcoded defaults in providers.
    """

    # ── Registry ──────────────────────────────────────────────────────
    enable_registry: bool = True
    auto_register_builtin_packs: bool = True

    # ── Manager ───────────────────────────────────────────────────────
    enable_skills: bool = True
    degraded_mode_allowed: bool = True
    max_skills_per_request: int = 5

    # ── Auto-routing ──────────────────────────────────────────────────
    enable_auto_routing: bool = True
    routing_fallback_to_general: bool = True
    routing_min_confidence: float = 0.3
    routing_max_results: int = 5

    # ── Skill Composition ─────────────────────────────────────────────
    enable_composition: bool = True
    composition_strategy: str = "merge"  # merge, priority, sequential
    composition_max_skills: int = 5

    # ── Project Detection ─────────────────────────────────────────────
    enable_project_detection: bool = True
    project_detection_depth: int = 3

    # ── Capability Detection ──────────────────────────────────────────
    enable_capability_detection: bool = True

    # ── Health & Metrics ──────────────────────────────────────────────
    enable_health_reporting: bool = True
    enable_metrics_collection: bool = True
    metrics_window_size: int = 1000

    # ── Hot Reload ────────────────────────────────────────────────────
    enable_hot_reload: bool = False
    hot_reload_poll_interval: float = 2.0

    # ── Logging ───────────────────────────────────────────────────────
    log_skills: bool = True
    log_routing: bool = True
    log_composition: bool = True

    # ── Any ───────────────────────────────────────────────────────
    max_neighbour_files: int = 10
    max_context_size: int = 65536

    # ── Additional overrides ──────────────────────────────────────────
    overrides: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def defaults(cls) -> SkillConfig:
        return cls()

    def merge(self, overrides: dict[str, Any]) -> SkillConfig:
        merged = {k: v for k, v in self.__dict__.items()}
        merged.update(overrides)
        return SkillConfig(**merged)
