"""
Skill types — data classes shared across the skills subsystem.

21_System_Contracts.md §4 — Data class patterns.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SkillMetadata:
    """Immutable metadata describing a Skill Pack."""

    name: str
    description: str
    supported_languages: tuple[str, ...] = ()
    supported_frameworks: tuple[str, ...] = ()
    supported_file_extensions: tuple[str, ...] = ()
    priority: int = 100


@dataclass(frozen=True)
class SkillCapability:
    """A named capability a Skill Pack exposes."""

    name: str
    description: str
    confidence: float = 1.0


@dataclass
class SkillResult:
    """Result of a single skill operation."""

    success: bool
    content: str = ""
    suggestions: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    @classmethod
    def ok(cls, content: str = "", **kwargs: Any) -> SkillResult:
        return cls(success=True, content=content, **kwargs)

    @classmethod
    def fail(cls, error: str, **kwargs: Any) -> SkillResult:
        return cls(success=False, errors=[error], **kwargs)


@dataclass
class SkillStatistics:
    """Aggregated usage statistics for a single Skill Pack."""

    total_requests: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    total_latency_ms: float = 0.0
    average_latency_ms: float = 0.0
    last_request_time: float = 0.0
    last_error: str | None = None

    def record(self, duration_ms: float, success: bool) -> None:
        self.total_requests += 1
        self.total_latency_ms += duration_ms
        if success:
            self.successful_executions += 1
        else:
            self.failed_executions += 1
        self.average_latency_ms = (
            self.total_latency_ms / self.total_requests
        )
        self.last_request_time = time.time()


@dataclass
class SkillHealthReport:
    """Health status of a single Skill Pack."""

    name: str
    is_healthy: bool
    registered: bool
    active: bool
    last_check: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def healthy(cls, name: str, **details: Any) -> SkillHealthReport:
        return cls(
            name=name,
            is_healthy=True,
            registered=True,
            active=True,
            last_check=time.time(),
            details=details,
        )

    @classmethod
    def unhealthy(
        cls, name: str, reason: str = "", **details: Any
    ) -> SkillHealthReport:
        return cls(
            name=name,
            is_healthy=False,
            registered=True,
            active=False,
            last_check=time.time(),
            details={"reason": reason, **details},
        )
