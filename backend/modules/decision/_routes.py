"""
Route targets and decision containers for the Decision Engine.

21_System_Contracts.md §4.2 — Decision contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RouteTarget(StrEnum):
    """Subsystem execution targets for user requests."""

    FAST_COMMAND_ROUTER = "FAST_COMMAND_ROUTER"
    CODING_AGENT = "CODING_AGENT"
    PLANNING_ENGINE = "PLANNING_ENGINE"
    LLM_CONVERSATION = "LLM_CONVERSATION"


@dataclass
class RouteDecision:
    """Routing decision produced by the Decision Engine."""

    target: RouteTarget
    confidence: float
    reason: str
