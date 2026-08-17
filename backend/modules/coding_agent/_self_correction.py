from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from backend.types import ToolResult
_LOG = logging.getLogger("naira.coding_agent.self_correction")


@dataclass
class CorrectionResult:
    success: bool
    iterations: int
    final_result: ToolResult
    corrections: list[dict[str, Any]] = field(default_factory=list)
    total_duration_ms: float = 0.0


class SelfCorrectionLoop:
    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
        enabled: bool = True,
        max_iterations: int = 3,
    ) -> None:
        self._logger = logger or _LOG
        self._enabled = enabled
        self._max_iterations = max_iterations
        self._total_corrections = 0
        self._successful_corrections = 0
        self._failed_corrections = 0
        self._degraded = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def degraded(self) -> bool:
        return self._degraded

    def degrade(self) -> None:
        self._degraded = True
        self._logger.warning("SelfCorrectionLoop marked degraded")

    async def execute_with_correction(
        self,
        task_id: str,
        task_description: str,
        execute_fn: Callable[[], Any],
        reflect_fn: Callable[[dict[str, Any], dict[str, Any]], Any],
        context: dict[str, Any] | None = None,
    ) -> CorrectionResult:
        start = time.monotonic()
        corrections: list[dict[str, Any]] = []
        current_context = dict(context or {})

        for iteration in range(1, self._max_iterations + 1):
            try:
                result = await execute_fn()
                if isinstance(result, ToolResult):
                    tool_status = result.status
                    tool_output = result.output or ""
                    tool_error = result.error
                elif isinstance(result, dict):
                    tool_status = result.get("status", "completed")
                    tool_output = result.get("output", "")
                    tool_error = result.get("error")
                else:
                    tool_status = "completed"
                    tool_output = str(result)
                    tool_error = None

                if tool_status == "success" or tool_status == "completed":
                    duration_ms = (time.monotonic() - start) * 1000
                    final_result = ToolResult(
                        status="success",
                        output=tool_output,
                    )
                    self._total_corrections += 1
                    self._successful_corrections += 1
                    return CorrectionResult(
                        success=True,
                        iterations=iteration,
                        final_result=final_result,
                        corrections=corrections,
                        total_duration_ms=duration_ms,
                    )

                if tool_status == "error" and tool_error:
                    should_correct, correction_plan = await self._analyze_error(
                        task_id, tool_error, iteration,
                    )
                    if not should_correct:
                        duration_ms = (time.monotonic() - start) * 1000
                        self._total_corrections += 1
                        self._failed_corrections += 1
                        return CorrectionResult(
                            success=False,
                            iterations=iteration,
                            final_result=ToolResult(status="error", error=tool_error),
                            corrections=corrections,
                            total_duration_ms=duration_ms,
                        )
                    corrections.append({
                        "iteration": iteration,
                        "error": tool_error,
                        "plan": correction_plan,
                    })
                    current_context["correction_history"] = corrections
                    self._logger.debug(
                        "Correction %d for task %s: %s",
                        iteration, task_id, correction_plan,
                    )
                    continue

                duration_ms = (time.monotonic() - start) * 1000
                self._total_corrections += 1
                self._successful_corrections += 1
                return CorrectionResult(
                    success=True,
                    iterations=iteration,
                    final_result=ToolResult(status="success", output=tool_output),
                    corrections=corrections,
                    total_duration_ms=duration_ms,
                )

            except Exception as exc:
                should_correct, correction_plan = await self._analyze_error(
                    task_id, str(exc), iteration,
                )
                if not should_correct:
                    duration_ms = (time.monotonic() - start) * 1000
                    self._total_corrections += 1
                    self._failed_corrections += 1
                    return CorrectionResult(
                        success=False,
                        iterations=iteration,
                        final_result=ToolResult(status="error", error=str(exc)),
                        corrections=corrections,
                        total_duration_ms=duration_ms,
                    )
                corrections.append({
                    "iteration": iteration,
                    "error": str(exc),
                    "plan": correction_plan,
                })
                current_context["correction_history"] = corrections
                self._logger.debug(
                    "Correction %d for task %s: %s",
                    iteration, task_id, correction_plan,
                )

        duration_ms = (time.monotonic() - start) * 1000
        self._total_corrections += 1
        self._failed_corrections += 1
        last_error = corrections[-1]["error"] if corrections else "Max iterations exceeded"
        return CorrectionResult(
            success=False,
            iterations=self._max_iterations,
            final_result=ToolResult(status="error", error=last_error),
            corrections=corrections,
            total_duration_ms=duration_ms,
        )

    async def _analyze_error(
        self,
        task_id: str,
        error: str,
        iteration: int,
    ) -> tuple[bool, str]:
        if iteration >= self._max_iterations:
            return False, "Max iterations reached"

        error_lower = error.lower()
        if "timeout" in error_lower:
            return True, "Increase timeout and retry"
        if "not found" in error_lower or "no such" in error_lower:
            return True, "Check path and create missing resource"
        if "permission" in error_lower or "denied" in error_lower:
            return True, "Retry with elevated permissions or different path"
        if "syntax" in error_lower:
            return True, "Fix syntax error and retry"
        if "import" in error_lower or "module" in error_lower:
            return True, "Install missing dependency and retry"

        return True, "Retry with adjusted parameters"

    def metrics(self) -> dict[str, Any]:
        return {
            "enabled": self._enabled,
            "degraded": self._degraded,
            "max_iterations": self._max_iterations,
            "total_corrections": self._total_corrections,
            "successful_corrections": self._successful_corrections,
            "failed_corrections": self._failed_corrections,
        }

    async def health_check(self) -> bool:
        return self._enabled and not self._degraded
