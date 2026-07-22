"""
Event types and data containers for the Analytics Engine.

21_System_Contracts.md §4.2 — Analytics data contracts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal


class EventType(StrEnum):
    """Standard analytics event category identifiers."""

    TOOL_CALL = "TOOL_CALL"
    FCR_HIT = "FCR_HIT"
    FCR_MISS = "FCR_MISS"
    LLM_FALLBACK = "LLM_FALLBACK"
    COMMAND_SUCCESS = "COMMAND_SUCCESS"
    COMMAND_FAILURE = "COMMAND_FAILURE"
    SESSION_START = "SESSION_START"
    SESSION_END = "SESSION_END"


@dataclass
class AnalyticsEvent:
    """Single recorded analytics event."""

    event_type: str
    timestamp: datetime = field(default_factory=datetime.now)
    payload: dict[str, Any] = field(default_factory=dict)
    duration_ms: float | None = None
    success: bool | None = None


@dataclass
class AnalyticsSummary:
    """Aggregated usage and performance metrics summary."""

    period: Literal["today", "week", "all"]
    total_events: int
    event_counts: dict[str, int]
    success_rate: float
    top_tools: list[tuple[str, int]]
    avg_duration_ms: float
