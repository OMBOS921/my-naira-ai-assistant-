"""
BaseSkillPack — abstract base for all Skill Pack implementations.

Provides default implementations for health() and metrics().
Subclasses override metadata(), capabilities(), and operation methods.
"""

from __future__ import annotations

import logging
import time
from abc import ABC

from backend.modules.coding_agent.skills._health import SkillHealthReport
from backend.modules.coding_agent.skills._skill_port import SkillPort
from backend.modules.coding_agent.skills._statistics import SkillStatistics
from backend.modules.coding_agent.skills._types import (
    SkillCapability,
    SkillMetadata,
    SkillResult,
)
from backend.modules.coding_agent.skills.context._models import SkillContext

_LOG = logging.getLogger("naira.coding_agent.skills.packs")


class BaseSkillPack(SkillPort, ABC):
    """Base implementation for all Skill Packs.

    Provides:
    - Built-in health() that reports healthy when initialised
    - Built-in metrics() tracking via SkillStatistics
    - Duration tracking for all operations
    """

    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
        metadata: SkillMetadata | None = None,
    ) -> None:
        self._logger = logger or _LOG
        self._stats = SkillStatistics()
        self._meta = metadata or self._default_metadata()
        self._healthy: bool = True

    # ── Subclass hooks ────────────────────────────────────────────────

    def _default_metadata(self) -> SkillMetadata:
        raise NotImplementedError(
            f"{type(self).__name__} must override _default_metadata()"
        )

    def _default_capabilities(self) -> list[SkillCapability]:
        return []

    async def _execute_analyse(self, context: SkillContext) -> SkillResult:
        return SkillResult.ok(content=f"{self._meta.name} analysis completed")

    async def _execute_plan(self, context: SkillContext) -> SkillResult:
        return SkillResult.ok(content=f"{self._meta.name} execution plan")

    async def _execute_review(self, context: SkillContext) -> SkillResult:
        return SkillResult.ok(content=f"{self._meta.name} review completed")

    async def _execute_generate(self, context: SkillContext) -> SkillResult:
        return SkillResult.ok(content=f"{self._meta.name} code generation")

    async def _execute_refactor(self, context: SkillContext) -> SkillResult:
        return SkillResult.ok(content=f"{self._meta.name} refactoring suggestions")

    async def _execute_debug(self, context: SkillContext) -> SkillResult:
        return SkillResult.ok(content=f"{self._meta.name} debug analysis")

    async def _execute_explain(self, context: SkillContext) -> SkillResult:
        return SkillResult.ok(content=f"{self._meta.name} explanation")

    # ── SkillPort implementation ──────────────────────────────────────

    def metadata(self) -> SkillMetadata:
        return self._meta

    def capabilities(self) -> list[SkillCapability]:
        return self._default_capabilities()

    async def analyse(self, context: SkillContext) -> SkillResult:
        return await self._timed("analyse", context)

    async def plan(self, context: SkillContext) -> SkillResult:
        return await self._timed("plan", context)

    async def review(self, context: SkillContext) -> SkillResult:
        return await self._timed("review", context)

    async def generate(self, context: SkillContext) -> SkillResult:
        return await self._timed("generate", context)

    async def refactor(self, context: SkillContext) -> SkillResult:
        return await self._timed("refactor", context)

    async def debug(self, context: SkillContext) -> SkillResult:
        return await self._timed("debug", context)

    async def explain(self, context: SkillContext) -> SkillResult:
        return await self._timed("explain", context)

    async def health(self) -> SkillHealthReport:
        return SkillHealthReport(
            name=self._meta.name,
            is_healthy=self._healthy,
            registered=True,
            active=True,
            last_check=time.time(),
            details={
                "priority": self._meta.priority,
                "languages": list(self._meta.supported_languages),
                "frameworks": list(self._meta.supported_frameworks),
                "statistics": {
                    "total_requests": self._stats.total_requests,
                    "successful": self._stats.successful_executions,
                    "failed": self._stats.failed_executions,
                    "average_latency_ms": round(self._stats.average_latency_ms, 2),
                },
            },
        )

    async def metrics(self) -> SkillStatistics:
        return self._stats

    # ── Internal ──────────────────────────────────────────────────────

    async def _timed(self, op: str, context: SkillContext) -> SkillResult:
        start = time.time()
        try:
            ops = {
                "analyse": self._execute_analyse,
                "plan": self._execute_plan,
                "review": self._execute_review,
                "generate": self._execute_generate,
                "refactor": self._execute_refactor,
                "debug": self._execute_debug,
                "explain": self._execute_explain,
            }
            method = ops.get(op)
            if method is None:
                return SkillResult.fail(f"Unknown operation: {op}")

            result = await method(context)
            duration_ms = (time.time() - start) * 1000
            result.duration_ms = duration_ms
            self._stats.record(duration_ms, result.success)
            return result
        except Exception as exc:
            duration_ms = (time.time() - start) * 1000
            self._stats.record(duration_ms, False)
            return SkillResult(
                success=False,
                errors=[f"{op}: {exc}"],
                duration_ms=duration_ms,
            )
