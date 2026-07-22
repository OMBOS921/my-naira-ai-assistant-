"""
Analytics Module — Naira-OS usage, tool execution, and latency tracking.

21_System_Contracts.md §4.2 — Analytics contracts.
"""

from __future__ import annotations

from backend.modules.analytics._event_types import (
    AnalyticsEvent,
    AnalyticsSummary,
    EventType,
)
from backend.modules.analytics.analytics_module import AnalyticsManager

__all__ = [
    "AnalyticsEvent",
    "AnalyticsManager",
    "AnalyticsSummary",
    "EventType",
]
