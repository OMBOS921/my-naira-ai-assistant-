from __future__ import annotations

import cProfile
import io
import logging
import pstats
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from backend.validation._types import PerformanceSnapshot

_LOG = logging.getLogger("naira.validation.performance")


@dataclass
class PerformanceRunner:
    _profiler: cProfile.Profile | None = None
    _results: list[PerformanceSnapshot] = field(default_factory=list)

    def profile_callable(
        self,
        label: str,
        fn: Callable[[], Any],
        *,
        iterations: int = 1,
    ) -> PerformanceSnapshot:
        prof = cProfile.Profile()
        prof.enable()
        mem_before = self._get_memory_mb()

        start = time.perf_counter()
        for _ in range(iterations):
            fn()
        wall = time.perf_counter() - start

        mem_after = self._get_memory_mb()
        prof.disable()

        buf = io.StringIO()
        stats = pstats.Stats(prof, stream=buf).sort_stats("cumtime")
        stats.print_stats(20)
        call_count = stats.total_calls if hasattr(stats, "total_calls") else 0

        snapshot = PerformanceSnapshot(
            label=label,
            cpu_time_s=stats.total_tt if hasattr(stats, "total_tt") else 0.0,
            wall_time_s=wall,
            memory_mb=max(0.0, mem_after - mem_before),
            call_count=call_count,
        )
        self._results.append(snapshot)
        return snapshot

    def profile_module_import(self, module_path: str) -> PerformanceSnapshot:
        label = f"import:{module_path}"
        mem_before = self._get_memory_mb()
        start = time.perf_counter()

        import importlib
        importlib.import_module(module_path)

        wall = time.perf_counter() - start
        mem_after = self._get_memory_mb()

        snapshot = PerformanceSnapshot(
            label=label,
            cpu_time_s=0.0,
            wall_time_s=wall,
            memory_mb=max(0.0, mem_after - mem_before),
            call_count=0,
        )
        return snapshot

    @staticmethod
    def _get_memory_mb() -> float:
        try:
            import psutil
            proc = psutil.Process()
            return proc.memory_info().rss / (1024 * 1024)
        except ImportError:
            return 0.0

    def report(self) -> str:
        if not self._results:
            return "No performance data collected."
        lines = ["Performance Report:"]
        for r in self._results:
            lines.append(
                f"  {r.label}: wall={r.wall_time_s*1000:.1f}ms "
                f"mem={r.memory_mb:.1f}MB calls={r.call_count}"
            )
        return "\n".join(lines)
