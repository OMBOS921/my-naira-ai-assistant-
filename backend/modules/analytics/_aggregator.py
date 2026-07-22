"""
In-memory aggregator for fast zero-latency analytics queries.

21_System_Contracts.md §4.2 — Performance requirements.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from backend.modules.analytics._event_types import AnalyticsEvent, AnalyticsSummary, EventType


class AnalyticsAggregator:
    """In-memory rolling counters for today, last 7 days, and all-time statistics."""

    def __init__(self) -> None:
        self._events_recent: list[AnalyticsEvent] = []  # max last 7 days
        self._all_time_counts: dict[str, int] = {}
        self._all_time_total: int = 0
        self._all_time_success_count: int = 0
        self._all_time_status_count: int = 0
        self._all_time_duration_sum: float = 0.0
        self._all_time_duration_count: int = 0
        self._all_time_tool_counts: dict[str, int] = {}

        self._fcr_hits: int = 0
        self._fcr_misses: int = 0
        self._llm_fallbacks: int = 0

    def update(self, event: AnalyticsEvent) -> None:
        """Update rolling in-memory counters with a new event."""
        # Clean up events older than 7 days from recent cache
        now = datetime.now()
        seven_days_ago = now - timedelta(days=7)
        self._events_recent = [e for e in self._events_recent if e.timestamp >= seven_days_ago]
        self._events_recent.append(event)

        # All-time counters
        ev_type = event.event_type
        self._all_time_counts[ev_type] = self._all_time_counts.get(ev_type, 0) + 1
        self._all_time_total += 1

        if event.success is not None:
            self._all_time_status_count += 1
            if event.success:
                self._all_time_success_count += 1

        if event.duration_ms is not None:
            self._all_time_duration_sum += event.duration_ms
            self._all_time_duration_count += 1

        if ev_type == EventType.TOOL_CALL:
            tool_name = event.payload.get("tool_name") or event.payload.get("tool")
            if tool_name:
                t_str = str(tool_name)
                self._all_time_tool_counts[t_str] = self._all_time_tool_counts.get(t_str, 0) + 1

        if ev_type == EventType.FCR_HIT:
            self._fcr_hits += 1
        elif ev_type == EventType.FCR_MISS:
            self._fcr_misses += 1
        elif ev_type == EventType.LLM_FALLBACK:
            self._llm_fallbacks += 1

    def get_fcr_effectiveness(self) -> float:
        """Calculate percentage of commands resolved by FCR vs LLM fallback."""
        denom = self._fcr_hits + self._llm_fallbacks + self._fcr_misses
        if denom == 0:
            return 0.0
        return self._fcr_hits / denom

    def get_intent_success_rate(self, intent_pattern: str) -> float:
        """Return success rate for a specific intent or tool pattern in recent events."""
        matching_events = [
            e for e in self._events_recent
            if e.success is not None and (
                intent_pattern in e.payload.get("intent", "") or
                intent_pattern in e.payload.get("target", "") or
                intent_pattern in e.payload.get("tool_name", "") or
                intent_pattern in e.event_type
            )
        ]
        if not matching_events:
            return 1.0  # default optimistic rate if no data
        succ_count = sum(1 for e in matching_events if e.success)
        return succ_count / len(matching_events)

    def get_summary(self, period: Literal["today", "week", "all"]) -> AnalyticsSummary:
        """Return summary computed from in-memory counters for recent periods."""
        now = datetime.now()
        if period == "today":
            start_time = datetime(now.year, now.month, now.day)
            events = [e for e in self._events_recent if e.timestamp >= start_time]
        elif period == "week":
            start_time = now - timedelta(days=7)
            events = [e for e in self._events_recent if e.timestamp >= start_time]
        else:
            # "all" period
            top_tools = sorted(
                self._all_time_tool_counts.items(), key=lambda x: x[1], reverse=True
            )[:5]
            succ_rate = (
                (self._all_time_success_count / self._all_time_status_count)
                if self._all_time_status_count > 0
                else 0.0
            )
            avg_dur = (
                (self._all_time_duration_sum / self._all_time_duration_count)
                if self._all_time_duration_count > 0
                else 0.0
            )
            return AnalyticsSummary(
                period="all",
                total_events=self._all_time_total,
                event_counts=dict(self._all_time_counts),
                success_rate=succ_rate,
                top_tools=top_tools,
                avg_duration_ms=avg_dur,
            )

        # Calculate for "today" or "week" from filtered recent events
        counts: dict[str, int] = {}
        tool_counts: dict[str, int] = {}
        status_count = 0
        succ_count = 0
        dur_sum = 0.0
        dur_count = 0

        for e in events:
            counts[e.event_type] = counts.get(e.event_type, 0) + 1
            if e.success is not None:
                status_count += 1
                if e.success:
                    succ_count += 1
            if e.duration_ms is not None:
                dur_sum += e.duration_ms
                dur_count += 1
            if e.event_type == EventType.TOOL_CALL:
                t_name = e.payload.get("tool_name") or e.payload.get("tool")
                if t_name:
                    t_str = str(t_name)
                    tool_counts[t_str] = tool_counts.get(t_str, 0) + 1

        top_tools = sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        succ_rate = (succ_count / status_count) if status_count > 0 else 0.0
        avg_dur = (dur_sum / dur_count) if dur_count > 0 else 0.0

        return AnalyticsSummary(
            period=period,
            total_events=len(events),
            event_counts=counts,
            success_rate=succ_rate,
            top_tools=top_tools,
            avg_duration_ms=avg_dur,
        )
