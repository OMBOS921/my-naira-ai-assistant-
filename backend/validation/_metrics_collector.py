from __future__ import annotations

import logging
import statistics
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from backend.validation._types import (
    CoverageData,
    LeakReport,
    PerformanceSnapshot,
    ValidationResult,
)

_LOG = logging.getLogger("naira.validation.metrics")


@dataclass
class MetricsCollector:
    _suite_times: dict[str, list[float]] = field(
        default_factory=lambda: defaultdict(list)
    )
    _pass_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    _fail_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    _performance_data: list[PerformanceSnapshot] = field(default_factory=list)
    _leak_data: list[LeakReport] = field(default_factory=list)
    _coverage_history: list[CoverageData] = field(default_factory=list)
    _start_time: float = field(default_factory=time.time)

    def record_result(self, result: ValidationResult) -> None:
        key = result.kind
        self._suite_times[key].append(result.duration_s)
        if result.passed:
            self._pass_counts[key] += 1
        else:
            self._fail_counts[key] += 1

    def record_performance(self, snapshot: PerformanceSnapshot) -> None:
        self._performance_data.append(snapshot)

    def record_leak(self, report: LeakReport) -> None:
        self._leak_data.append(report)

    def record_coverage(self, data: CoverageData) -> None:
        self._coverage_history.append(data)

    @property
    def pass_rate(self) -> float:
        total_p = sum(self._pass_counts.values())
        total_f = sum(self._fail_counts.values())
        total = total_p + total_f
        if total == 0:
            return 1.0
        return total_p / total

    @property
    def average_suite_time(self) -> dict[str, float]:
        result: dict[str, float] = {}
        for key, times in self._suite_times.items():
            result[key] = statistics.mean(times) if times else 0.0
        return result

    @property
    def flaky_suites(self) -> list[str]:
        flaky: list[str] = []
        for key in self._suite_times:
            total = self._pass_counts[key] + self._fail_counts[key]
            if total >= 3:
                fails = self._fail_counts[key]
                if 0 < fails < total:
                    flaky.append(key)
        return flaky

    @property
    def total_runtime_s(self) -> float:
        return time.time() - self._start_time

    def summary(self) -> str:
        total_p = sum(self._pass_counts.values())
        total_f = sum(self._fail_counts.values())
        total_t = total_p + total_f
        lines: list[str] = []
        lines.append(f"Total {total_t} results — {total_p} passed, {total_f} failed")
        lines.append(f"Pass rate: {self.pass_rate * 100:.1f}%")
        lines.append(f"Runtime: {self.total_runtime_s:.1f}s")

        if self._performance_data:
            lines.append("Performance:")
            for d in self._performance_data:
                lines.append(
                    f"  {d.label}: {d.wall_time_s * 1000:.1f}ms wall, "
                    f"{d.memory_mb:.1f}MB"
                )

        if self._leak_data:
            lines.append(f"Leaks detected: {len(self._leak_data)}")

        if self._coverage_history:
            last = self._coverage_history[-1]
            lines.append(f"Coverage: {last.coverage_pct:.1f}%")

        flaky = self.flaky_suites
        if flaky:
            lines.append(f"Flaky suites: {', '.join(flaky)}")

        return "\n".join(lines)
