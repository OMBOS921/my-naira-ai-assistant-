"""Health Reporting — monitors and reports the health of context services.

Provides comprehensive health checks for all Any Intelligence
services, aggregating individual service health into a unified report.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from backend.modules.context_intelligence._types import HealthReport

_LOG = logging.getLogger("naira.context_intelligence.health_reporting")

_HealthCheckFn = Callable[[], bool]


class HealthReporting:
    """Monitors and reports health of context intelligence services.

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
        self._checks: dict[str, _HealthCheckFn] = {}
        self._service_names: list[str] = []
        self._degraded = False
        self._last_check_results: dict[str, Any] = {}

    def register_service(self, name: str, health_check_fn: _HealthCheckFn) -> None:
        """Register a service for health monitoring.

        Parameters
        ----------
        name : str
            Service name.
        health_check_fn : Callable[[], bool]
            Async or sync function that returns health status.
        """
        if name not in self._service_names:
            self._service_names.append(name)
        self._checks[name] = health_check_fn

    def mark_degraded(self) -> None:
        """Mark the health reporting as degraded."""
        self._degraded = True

    async def generate_report(self) -> HealthReport:
        """Generate a comprehensive health report.

        Parameters
        ----------
        Returns
        -------
        HealthReport
            Aggregated health report.
        """
        checks: dict[str, dict[str, Any]] = {}
        healthy_count = 0
        total_count = len(self._service_names) or 1

        for name in self._service_names:
            check_fn = self._checks.get(name)
            if check_fn is None:
                checks[name] = {
                    "healthy": False,
                    "error": "No health check registered",
                }
                continue

            try:
                result = check_fn()
                if asyncio.iscoroutine(result):
                    result = await result
                is_healthy = bool(result)
                if is_healthy:
                    healthy_count += 1
                checks[name] = {
                    "healthy": is_healthy,
                    "available": is_healthy,
                }
            except Exception as exc:
                checks[name] = {
                    "healthy": False,
                    "error": str(exc),
                }

        self._last_check_results = checks

        all_healthy = healthy_count == total_count and not self._degraded

        return HealthReport(
            healthy=all_healthy,
            degraded=self._degraded,
            services_online=healthy_count,
            services_total=total_count,
            checks=checks,
        )

    def generate_report_sync(self) -> HealthReport:
        """Synchronous version of ``generate_report`` for use from non-async code."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.generate_report())
        # Running loop present — run in a separate thread to avoid blocking
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, self.generate_report())
            return future.result()

    @property
    def degraded(self) -> bool:
        return self._degraded

    @property
    def service_count(self) -> int:
        return len(self._service_names)

    async def health_check(self) -> bool:
        report = await self.generate_report()
        return report.healthy
