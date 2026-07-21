"""Metrics Collection — collects, aggregates, and exposes performance metrics.

Gathers metrics from all Context Intelligence services and provides
snapshots for monitoring, debugging, and performance analysis.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from typing import Any

from backend.modules.context_intelligence._types import MetricsSnapshot

_LOG = logging.getLogger("naira.context_intelligence.metrics")

_MAX_METRIC_HISTORY = 1000


class MetricsCollector:
    """Collects and exposes metrics for the Context Intelligence layer.

    Parameters
    ----------
    logger : logging.Logger | None
        Module-scoped logger.
    """

    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._logger = logger or _LOG
        self._counters: dict[str, int] = {}
        self._gauges: dict[str, float] = {}
        self._histories: dict[str, deque[float]] = {}
        self._start_time = time.monotonic()

    def increment(self, name: str, value: int = 1) -> None:
        """Increment a counter metric.

        Parameters
        ----------
        name : str
            Metric name.
        value : int
            Amount to increment by.
        """
        self._counters[name] = self._counters.get(name, 0) + value

    def set_gauge(self, name: str, value: float) -> None:
        """Set a gauge metric to a specific value.

        Parameters
        ----------
        name : str
            Metric name.
        value : float
            Gauge value.
        """
        self._gauges[name] = value

    def record_value(self, name: str, value: float) -> None:
        """Record a timed/histogram value.

        Parameters
        ----------
        name : str
            Metric name.
        value : float
            Value to record (e.g., duration in ms).
        """
        if name not in self._histories:
            self._histories[name] = deque(maxlen=_MAX_METRIC_HISTORY)
        self._histories[name].append(value)

    def get_counter(self, name: str) -> int:
        """Get the current value of a counter.

        Parameters
        ----------
        name : str
            Metric name.

        Returns
        -------
        int
            Current counter value.
        """
        return self._counters.get(name, 0)

    def get_gauge(self, name: str) -> float:
        """Get the current value of a gauge.

        Parameters
        ----------
        name : str
            Metric name.

        Returns
        -------
        float
            Current gauge value.
        """
        return self._gauges.get(name, 0.0)

    def get_average(self, name: str) -> float:
        """Get the average of recorded values for a metric.

        Parameters
        ----------
        name : str
            Metric name.

        Returns
        -------
        float
            Average of recorded values, or 0.0 if none.
        """
        history = self._histories.get(name)
        if not history:
            return 0.0
        return sum(history) / len(history)

    def snapshot(self) -> MetricsSnapshot:
        """Take a snapshot of all current metrics.

        Returns
        -------
        MetricsSnapshot
            All current metrics.
        """
        snapshot = MetricsSnapshot(
            timestamp=time.time(),
            values={},
            counters=dict(self._counters),
            gauges=dict(self._gauges),
        )

        for name, history in self._histories.items():
            if history:
                snapshot.values[f"{name}_avg"] = round(
                    sum(history) / len(history), 4
                )
                snapshot.values[f"{name}_min"] = round(min(history), 4)
                snapshot.values[f"{name}_max"] = round(max(history), 4)
                snapshot.values[f"{name}_count"] = len(history)

        snapshot.gauges["uptime_seconds"] = round(
            time.monotonic() - self._start_time, 2
        )

        return snapshot

    def to_dict(self) -> dict[str, Any]:
        """Return metrics as a flat dictionary.

        Returns
        -------
        dict[str, Any]
            Metrics dictionary for serialisation.
        """
        snap = self.snapshot()
        result: dict[str, Any] = {
            "counters": snap.counters,
            "gauges": snap.gauges,
        }
        result.update(snap.values)
        return result

    def reset(self) -> None:
        """Reset all metrics."""
        self._counters.clear()
        self._gauges.clear()
        self._histories.clear()
        self._start_time = time.monotonic()

    async def health_check(self) -> bool:
        return True
