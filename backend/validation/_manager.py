from __future__ import annotations

import asyncio
import datetime
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.validation._async_inspector import AsyncInspector
from backend.validation._auto_fix_coordinator import AutoFixCoordinator
from backend.validation._bug_reporter import BugReporter
from backend.validation._coverage_reporter import CoverageReporter
from backend.validation._leak_detector import LeakDetector
from backend.validation._metrics_collector import MetricsCollector
from backend.validation._performance_runner import PerformanceRunner
from backend.validation._regression_runner import RegressionRunner
from backend.validation._resource_inspector import ResourceInspector
from backend.validation._runner import ValidationRunner
from backend.validation._types import (
    ValidationKind,
    ValidationReport,
    ValidationResult,
)
from backend.validation._validation_history import ValidationHistory

_LOG = logging.getLogger("naira.validation.manager")
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent


def _resolve_path(p: str) -> Path:
    target = Path(p)
    if not target.is_absolute():
        target = _PROJECT_ROOT / target
    return target


_KIND_MAP: dict[ValidationKind, tuple[str, ...]] = {
    "unit": ("testing/unit/",),
    "integration": ("testing/integration/",),
    "eventbus": ("testing/unit/test_eventbus.py",),
    "capability": ("testing/unit/modules/capability/",),
    "tool": ("testing/unit/modules/tools/",),
    "health": ("testing/integration/test_boot_sequence.py",),
    "config": ("testing/unit/modules/settings/",),
    "provider": ("testing/unit/modules/llm/",),
    "skill": ("testing/unit/modules/coding_agent/skills/",),
    "coding_agent": ("testing/unit/modules/coding_agent/",),
    "voice": ("testing/unit/modules/voice/",),
    "vision": ("testing/unit/modules/vision/",),
    "browser": ("testing/unit/modules/browser/",),
    "pc_control": ("testing/unit/modules/pc_control/",),
    "context_intelligence": ("testing/unit/modules/context_intelligence/",),
}

_ALL_KINDS: list[ValidationKind] = [
    "unit", "integration", "eventbus", "capability", "tool",
    "health", "config", "provider", "skill", "coding_agent",
    "voice", "vision", "browser", "pc_control", "context_intelligence",
]


@dataclass
class ValidationManager:
    bug_reporter: BugReporter = field(default_factory=BugReporter)
    metrics: MetricsCollector = field(default_factory=MetricsCollector)
    history: ValidationHistory = field(default_factory=ValidationHistory)
    async_inspector: AsyncInspector = field(default_factory=AsyncInspector)
    leak_detector: LeakDetector = field(default_factory=LeakDetector)
    resource_inspector: ResourceInspector = field(default_factory=ResourceInspector)
    performance_runner: PerformanceRunner = field(default_factory=PerformanceRunner)
    regression_runner: RegressionRunner = field(default_factory=RegressionRunner)
    coverage_reporter: CoverageReporter = field(default_factory=CoverageReporter)
    auto_fix: AutoFixCoordinator | None = None
    max_auto_fix_cycles: int = 3
    run_async_inspection: bool = True
    run_leak_detection: bool = False
    run_performance: bool = False
    run_coverage: bool = False
    run_regression: bool = True
    concurrency: int = 2
    _started_at: datetime.datetime | None = None
    _finished_at: datetime.datetime | None = None

    def __post_init__(self) -> None:
        if self.auto_fix is None:
            self.auto_fix = AutoFixCoordinator(bug_reporter=self.bug_reporter)

    async def run_all(self) -> ValidationReport:
        self._started_at = datetime.datetime.now(datetime.timezone.utc)
        run_id = str(uuid.uuid4())[:12]
        _LOG.info("Validation run %s started", run_id)

        available = [k for k in _ALL_KINDS if self._has_tests(k)]
        skipped = [k for k in _ALL_KINDS if k not in available]
        for k in skipped:
            _LOG.info("Skipping %s — no test paths found", k)

        all_results: list[ValidationResult] = []

        if available:
            all_test_paths: list[str] = []
            for k in available:
                all_test_paths.extend(_KIND_MAP[k])
            _LOG.info(
                "Running %d suite(s) in a single pytest: %s",
                len(available), ", ".join(available),
            )
            bulk = await self._run_pytest_bulk(tuple(available), tuple(all_test_paths))
            all_results.extend(bulk)
            for r in bulk:
                self.metrics.record_result(r)

        retries = await self._run_auto_fix_cycles(all_results, available)
        all_results.extend(retries)

        if self.run_async_inspection:
            self._inspect_async()

        if self.run_leak_detection:
            self._detect_leaks()

        coverage_pct = None
        if self.run_coverage:
            coverage_pct = await self._measure_coverage()

        if self.run_regression:
            regression_results = self._run_regression()
            all_results.extend(regression_results)
            for r in regression_results:
                self.metrics.record_result(r)

        self._finished_at = datetime.datetime.now(datetime.timezone.utc)
        total_passed = sum(1 for r in all_results if r.passed)
        total_failed = sum(1 for r in all_results if not r.passed)
        total_duration = (
            self._finished_at - self._started_at
        ).total_seconds()

        report = ValidationReport(
            run_id=run_id,
            started_at=self._started_at,
            finished_at=self._finished_at,
            results=tuple(all_results),
            total_passed=total_passed,
            total_failed=total_failed,
            total_skipped=0,
            total_duration_s=total_duration,
            coverage_pct=coverage_pct,
        )
        self.history.store_report(report)
        _LOG.info(
            "Validation %s — %d passed, %d failed, %.1fs",
            "PASSED" if report.all_passed else "FAILED",
            total_passed, total_failed, total_duration,
        )
        return report

    async def _run_pytest_bulk(
        self,
        kinds: tuple[ValidationKind, ...],
        test_paths: tuple[str, ...],
    ) -> list[ValidationResult]:
        loop = asyncio.get_running_loop()

        def _run() -> list[ValidationResult]:
            runner = ValidationRunner(
                kind="unit",
                name="bulk_suite",
                test_paths=test_paths,
            )
            result = runner.run()
            return [result]

        return await loop.run_in_executor(None, _run)

    def _inspect_async(self) -> None:
        issues = self.async_inspector.inspect()
        if not issues:
            return
        _LOG.warning("Async inspection found %d issue(s)", len(issues))
        seen: set[str] = set()
        for issue in issues:
            key = f"{issue.file_path}:{issue.line_number}:{issue.kind}"
            if key in seen:
                continue
            seen.add(key)
            sev = "high" if issue.kind in ("blocking_call_in_async", "missing_await") else "medium"
            self.bug_reporter.report(
                title=f"Async: {issue.kind}",
                severity=sev,
                file_path=issue.file_path,
                description=issue.description,
                line_number=issue.line_number,
            )

    def _detect_leaks(self) -> None:
        for report in self.leak_detector.detect_memory_leaks():
            self.metrics.record_leak(report)
            self.bug_reporter.report(
                title=f"Leak: {report.leak_type}",
                severity=report.severity,
                file_path="",
                description=report.description,
            )
        for report in self.leak_detector.detect_thread_leaks():
            self.metrics.record_leak(report)
            self.bug_reporter.report(
                title=f"Leak: {report.leak_type}",
                severity=report.severity,
                file_path="",
                description=report.description,
            )
        self.leak_detector.cleanup()

    async def _measure_coverage(self) -> float | None:
        _LOG.info("Measuring coverage ...")
        loop = asyncio.get_running_loop()
        coverage = await loop.run_in_executor(None, self.coverage_reporter.measure)
        if coverage is not None:
            self.metrics.record_coverage(coverage)
            return coverage.coverage_pct
        return None

    def _run_regression(self) -> list[ValidationResult]:
        results: list[ValidationResult] = []
        prev = self.regression_runner.load_baseline()
        if prev is not None:
            current = self.regression_runner.run_full_suite()
            results.append(current)
            self.metrics.record_result(current)
        new_base = self.regression_runner.run_full_suite()
        results.append(new_base)
        self.metrics.record_result(new_base)
        self.regression_runner.save_baseline()
        return results

    def _has_tests(self, kind: ValidationKind) -> bool:
        paths = _KIND_MAP.get(kind)
        if not paths:
            return False
        return any(_resolve_path(p).exists() for p in paths)

    async def _run_auto_fix_cycles(
        self,
        existing: list[ValidationResult],
        available: list[ValidationKind],
    ) -> list[ValidationResult]:
        if self.auto_fix is None:
            return []
        retries: list[ValidationResult] = []
        failed = {r.kind for r in existing if not r.passed and r.kind in available}
        for kind in failed:
            for cycle in range(self.max_auto_fix_cycles):
                _LOG.info("Auto-fix cycle %d/%d for %s", cycle + 1, self.max_auto_fix_cycles, kind)
                if not self.auto_fix.attempt_fix(
                    ValidationResult(
                        kind=kind, name=kind, passed=False, duration_s=0.0,
                        failures=("auto-fix trigger",), traces=(), logs=(),
                    )
                ):
                    break
                paths = _KIND_MAP.get(kind, ())
                if paths:
                    loop = asyncio.get_running_loop()
                    runner = ValidationRunner(kind=kind, name=kind, test_paths=paths)
                    retry = await loop.run_in_executor(None, runner.run)
                    retries.append(retry)
                    if retry.passed:
                        _LOG.info("Auto-fix succeeded for %s", kind)
                        break
            self.auto_fix.reset()
        return retries

    def generate_report(self) -> str:
        lines: list[str] = []
        lines.append("=" * 60)
        lines.append("VALIDATION AGENT REPORT")
        lines.append("=" * 60)

        if self._started_at:
            lines.append(f"Started:   {self._started_at.isoformat()}")
        if self._finished_at:
            lines.append(f"Finished:  {self._finished_at.isoformat()}")

        lines.append("")
        lines.append(self.metrics.summary())

        bug_summary = self.bug_reporter.summary()
        lines.append("")
        lines.append(bug_summary)

        last_run = self.history.last_run_passed
        if last_run is not None:
            lines.append(f"\nLast run: {'PASSED' if last_run else 'FAILED'}")

        recent = self.history.get_recent_runs(3)
        if recent:
            lines.append("\nRecent runs:")
            for r in recent:
                status = "PASS" if r["total_failed"] == 0 else "FAIL"
                lines.append(
                    f"  {r['run_id']}: {status} "
                    f"({r['total_passed']}p/{r['total_failed']}f) "
                    f"in {r['total_duration_s']:.1f}s"
                )

        lines.append("\n" + "=" * 60)
        return "\n".join(lines)
