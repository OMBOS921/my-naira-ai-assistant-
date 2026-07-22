"""
AnalyticsManager — central public manager for the analytics module.

21_System_Contracts.md §4.2 — ModuleInterface protocol.
18_Boot_Sequence.md §2 — Boot sequence.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Literal

from backend.modules.analytics._aggregator import AnalyticsAggregator
from backend.modules.analytics._event_types import AnalyticsEvent, AnalyticsSummary
from backend.modules.analytics._store import SQLiteAnalyticsStore

_LOG = logging.getLogger("naira.analytics")
DEFAULT_DB_FILENAME = "naira_analytics.db"


class AnalyticsManager:
    """Central analytics manager — tracks tool calls, latency, and system metrics.

    Conforms to ``ModuleInterface`` (``backend/types.py``).

    Parameters
    ----------
    config : object | None
        Application configuration.
    logger : logging.Logger | None
        Module-scoped logger.
    event_bus : object | None
        Event bus instance for subscribing to runtime events.
    db_path : Path | str | None
        Path to SQLite analytics database file.
    """

    def __init__(
        self,
        *,
        config: object | None = None,
        logger: logging.Logger | None = None,
        event_bus: object | None = None,
        db_path: Path | str | None = None,
    ) -> None:
        self._config = config
        self._logger = logger or _LOG
        self._event_bus = event_bus
        self._degraded: bool = False

        resolved_db = (
            Path(db_path) if db_path else Path.cwd() / "memory" / DEFAULT_DB_FILENAME
        )
        self._store = SQLiteAnalyticsStore(resolved_db)
        self._aggregator = AnalyticsAggregator()

    # ------------------------------------------------------------------
    # Module lifecycle (ModuleInterface protocol)
    # ------------------------------------------------------------------

    async def async_init(self) -> None:
        """Open SQLite analytics store and initialize schema."""
        try:
            await asyncio.to_thread(self._store.open)
            self._logger.info("Analytics SQLite store opened — path=%s", self._store._db_path)
        except Exception as exc:
            self._logger.error("Failed to open Analytics SQLite store: %s", exc)
            self._degraded = True
            return

        self._logger.info("AnalyticsManager initialised")

    async def async_shutdown(self) -> None:
        """Close SQLite analytics store connection."""
        try:
            await asyncio.to_thread(self._store.close)
            self._logger.info("Analytics SQLite store closed")
        except Exception as exc:
            self._logger.warning("Failed to close Analytics store: %s", exc)

        self._degraded = False

    def degrade(self) -> None:
        """Mark module as degraded after non-fatal failure."""
        self._store.close()
        self._degraded = True
        self._logger.warning("AnalyticsManager marked degraded")

    @property
    def degraded(self) -> bool:
        return self._degraded

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(self, event: AnalyticsEvent) -> None:
        """Fire-and-forget event recording.

        Updates in-memory aggregator synchronously and dispatches DB write asynchronously.
        Must never raise an exception or block the caller.
        """
        if self._degraded:
            return

        try:
            self._aggregator.update(event)
            # Dispatch DB write without blocking
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(asyncio.to_thread(self._store.write_event, event))
            except RuntimeError:
                # If no running event loop, execute fallback or ignore
                pass
        except Exception as exc:
            self._logger.warning("Failed to record analytics event: %s", exc)

    def get_summary(self, period: Literal["today", "week", "all"] = "all") -> AnalyticsSummary:
        """Return analytics summary for the specified time period."""
        if self._degraded:
            return AnalyticsSummary(
                period=period,
                total_events=0,
                event_counts={},
                success_rate=0.0,
                top_tools=[],
                avg_duration_ms=0.0,
            )

        return self._aggregator.get_summary(period)

    def get_fcr_effectiveness(self) -> float:
        """Return percentage of commands resolved by FCR vs LLM fallback."""
        if self._degraded:
            return 0.0
        return self._aggregator.get_fcr_effectiveness()

    def get_intent_success_rate(self, intent_pattern: str) -> float:
        """Return historical success rate for a specific intent pattern."""
        if self._degraded:
            return 1.0
        return self._aggregator.get_intent_success_rate(intent_pattern)
