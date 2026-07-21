from __future__ import annotations

import dataclasses
import datetime
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Literal


ValidationKind = Literal[
    "unit",
    "integration",
    "regression",
    "stress",
    "performance",
    "leak",
    "async",
    "resource",
    "coverage",
    "eventbus",
    "capability",
    "tool",
    "health",
    "config",
    "dependency",
    "provider",
    "skill",
    "coding_agent",
    "voice",
    "vision",
    "browser",
    "pc_control",
    "context_intelligence",
    "session_persistence",
    "mcp",
    "reflection",
    "planning",
]
AutoFixStatus = Literal["none", "attempted", "succeeded", "failed"]


@dataclasses.dataclass(frozen=True)
class ValidationResult:
    kind: ValidationKind
    name: str
    passed: bool
    duration_s: float
    failures: tuple[str, ...]
    traces: tuple[str, ...]
    logs: tuple[str, ...]
    auto_fix_status: AutoFixStatus = "none"
    timestamp: datetime.datetime = dataclasses.field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    @property
    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"[{status}] {self.kind}/{self.name}  ({self.duration_s:.2f}s)"


@dataclasses.dataclass(frozen=True)
class ValidationReport:
    run_id: str
    started_at: datetime.datetime
    finished_at: datetime.datetime | None
    results: tuple[ValidationResult, ...]
    total_passed: int
    total_failed: int
    total_skipped: int
    total_duration_s: float
    coverage_pct: float | None

    @property
    def all_passed(self) -> bool:
        return self.total_failed == 0


@dataclasses.dataclass(frozen=True)
class BugReport:
    id: str
    title: str
    severity: Literal["critical", "high", "medium", "low"]
    file_path: str
    line_number: int | None
    description: str
    traceback: str
    logs: tuple[str, ...]
    suggested_fix: str | None
    auto_fix_applied: bool
    auto_fix_success: bool


@dataclasses.dataclass(frozen=True)
class CoverageData:
    lines_total: int
    lines_covered: int
    branches_total: int
    branches_covered: int
    coverage_pct: float
    per_module: dict[str, float]

    @property
    def line_coverage_pct(self) -> float:
        if self.lines_total == 0:
            return 100.0
        return self.lines_covered / self.lines_total * 100.0


@dataclasses.dataclass(frozen=True)
class PerformanceSnapshot:
    label: str
    cpu_time_s: float
    wall_time_s: float
    memory_mb: float
    call_count: int


@dataclasses.dataclass(frozen=True)
class LeakReport:
    leak_type: Literal["memory", "async", "thread", "resource"]
    description: str
    severity: Literal["critical", "high", "medium", "low"]
    evidence: str


@dataclasses.dataclass(frozen=True)
class AsyncIssue:
    kind: Literal[
        "coroutine_not_awaited",
        "blocking_call_in_async",
        "sync_context_manager_on_async_lock",
        "missing_await",
        "fire_and_forget_coroutine",
    ]
    file_path: str
    line_number: int
    description: str


CostFn = Callable[[], dict[str, float]]
ValidateFn = Callable[[], ValidationResult]
