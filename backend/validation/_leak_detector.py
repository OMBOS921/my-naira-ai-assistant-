from __future__ import annotations

import gc
import logging
import os
import threading
import time
import tracemalloc
from dataclasses import dataclass, field
from typing import Any

from backend.validation._types import LeakReport

_LOG = logging.getLogger("naira.validation.leak_detector")


@dataclass
class LeakDetector:
    iterations: int = 5
    settle_time_s: float = 0.5
    growth_threshold_pct: float = 15.0
    _snapshots: list[dict[str, Any]] = field(default_factory=list)
    _tracemalloc_started: bool = False

    def detect_memory_leaks(self, setup_fn: Any = None) -> list[LeakReport]:
        reports: list[LeakReport] = []
        if not tracemalloc.is_tracing():
            tracemalloc.start()
            self._tracemalloc_started = True

        gc.collect()
        before = tracemalloc.take_snapshot()

        for i in range(self.iterations):
            if setup_fn:
                try:
                    setup_fn()
                except Exception:
                    pass
            gc.collect()
            time.sleep(self.settle_time_s)

        gc.collect()
        after = tracemalloc.take_snapshot()

        stats = after.compare_to(before, "lineno")
        top_growth = stats[:10] if stats else []
        total_size_increase = sum(s.size_diff for s in stats) if stats else 0

        if total_size_increase > 0:
            pct = (total_size_increase / max(before.statistics("lineno")[0].size if before.statistics("lineno") else 1, 1)) * 100
            if pct > self.growth_threshold_pct:
                evidence_lines = [str(s) for s in top_growth[:5]]
                reports.append(
                    LeakReport(
                        leak_type="memory",
                        description=f"Memory grew by {total_size_increase / 1024:.1f}KB "
                            f"({pct:.1f}%) over {self.iterations} iterations",
                        severity="high" if pct > 30 else "medium",
                        evidence="\n".join(evidence_lines),
                    )
                )

        return reports

    def detect_thread_leaks(self) -> list[LeakReport]:
        reports: list[LeakReport] = []
        before = set(threading.enumerate())
        gc.collect()
        time.sleep(self.settle_time_s)
        after = set(threading.enumerate())
        leaked = after - before
        if leaked:
            threads_str = "\n".join(str(t) for t in leaked)
            reports.append(
                LeakReport(
                    leak_type="thread",
                    description=f"{len(leaked)} thread(s) not cleaned up",
                    severity="high",
                    evidence=threads_str,
                )
            )
        return reports

    def detect_async_leaks(
        self, coroutine_objects: list[Any] | None = None
    ) -> list[LeakReport]:
        reports: list[LeakReport] = []
        gc.collect()
        pending = [
            obj for obj in gc.get_objects()
            if hasattr(obj, "__class__")
            and "coroutine" in type(obj).__name__
        ]
        if coroutine_objects:
            pending = [c for c in pending if id(c) in [id(x) for x in coroutine_objects]]

        if pending:
            evidence = "\n".join(
                f"{type(c).__name__} at {hex(id(c))}" for c in pending[:10]
            )
            reports.append(
                LeakReport(
                    leak_type="async",
                    description=f"{len(pending)} pending coroutine object(s) found in gc",
                    severity="high",
                    evidence=evidence,
                )
            )
        return reports

    def cleanup(self) -> None:
        if self._tracemalloc_started and tracemalloc.is_tracing():
            tracemalloc.stop()
            self._tracemalloc_started = False
