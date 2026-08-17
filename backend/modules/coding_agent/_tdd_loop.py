from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from backend.modules.coding_agent._exceptions import TDDError, TDDTestFailureError
from backend.types import ToolResult
_LOG = logging.getLogger("naira.coding_agent.tdd")


@dataclass
class TDDPhase:
    name: str
    status: str
    output: str
    duration_ms: float


@dataclass
class TDDResult:
    success: bool
    phases: list[TDDPhase] = field(default_factory=list)
    iterations: int = 0
    total_duration_ms: float = 0.0
    final_output: str = ""


class TDDLoop:
    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
        enabled: bool = True,
        max_iterations: int = 5,
    ) -> None:
        self._logger = logger or _LOG
        self._enabled = enabled
        self._max_iterations = max_iterations
        self._total_cycles = 0
        self._successful_cycles = 0
        self._failed_cycles = 0
        self._degraded = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def degraded(self) -> bool:
        return self._degraded

    def degrade(self) -> None:
        self._degraded = True
        self._logger.warning("TDDLoop marked degraded")

    async def execute_tdd(
        self,
        feature_description: str,
        write_test_fn: Callable[[str], Any],
        run_test_fn: Callable[[], Any],
        write_code_fn: Callable[[str], Any],
        refactor_fn: Callable[[], Any] | None = None,
    ) -> TDDResult:
        self._total_cycles += 1
        start = time.monotonic()
        phases: list[TDDPhase] = []

        try:
            phase_start = time.monotonic()
            test_result = await write_test_fn(feature_description)
            test_output = (
                test_result.output
                if isinstance(test_result, ToolResult)
                else str(test_result)
            )
            phases.append(TDDPhase(
                name="write_test",
                status="completed",
                output=test_output,
                duration_ms=(time.monotonic() - phase_start) * 1000,
            ))

            if not self._enabled:
                phases.append(TDDPhase(
                    name="run_test",
                    status="skipped",
                    output="TDD disabled, skipping test execution",
                    duration_ms=0.0,
                ))
                phases.append(TDDPhase(
                    name="write_code",
                    status="completed",
                    output=test_output,
                    duration_ms=0.0,
                ))
                result = TDDResult(
                    success=True, phases=phases,
                    iterations=1, final_output=test_output,
                    total_duration_ms=(time.monotonic() - start) * 1000,
                )
                self._successful_cycles += 1
                return result

            phase_start = time.monotonic()
            run_result = await run_test_fn()
            run_output = (
                run_result.output
                if isinstance(run_result, ToolResult)
                else str(run_result)
            )
            run_success = (
                (run_result.status == "success")
                if isinstance(run_result, ToolResult)
                else True
            )
            phases.append(TDDPhase(
                name="run_test",
                status="completed" if run_success else "failed",
                output=run_output,
                duration_ms=(time.monotonic() - phase_start) * 1000,
            ))

            iteration = 1
            while not run_success and iteration <= self._max_iterations:
                phase_start = time.monotonic()
                code_result = await write_code_fn(run_output)
                code_output = (
                    code_result.output if isinstance(code_result, ToolResult)
                    else str(code_result)
                )
                phases.append(TDDPhase(
                    name="write_code",
                    status="completed",
                    output=code_output,
                    duration_ms=(time.monotonic() - phase_start) * 1000,
                ))

                phase_start = time.monotonic()
                run_result = await run_test_fn()
                run_output = (
                    run_result.output
                    if isinstance(run_result, ToolResult)
                    else str(run_result)
                )
                run_success = (
                    (run_result.status == "success")
                    if isinstance(run_result, ToolResult)
                    else True
                )
                phases.append(TDDPhase(
                    name="run_test",
                    status="completed" if run_success else "failed",
                    output=run_output,
                    duration_ms=(time.monotonic() - phase_start) * 1000,
                ))
                iteration += 1

            if not run_success:
                self._failed_cycles += 1
                total_ms = (time.monotonic() - start) * 1000
                raise TDDTestFailureError(
                    f"Tests failed after {iteration - 1} iterations",
                    context={"feature": feature_description, "iterations": iteration - 1},
                )

            if refactor_fn:
                phase_start = time.monotonic()
                refactor_result = await refactor_fn()
                refactor_output = (
                    refactor_result.output if isinstance(refactor_result, ToolResult)
                    else str(refactor_result)
                )
                phases.append(TDDPhase(
                    name="refactor",
                    status="completed",
                    output=refactor_output,
                    duration_ms=(time.monotonic() - phase_start) * 1000,
                ))

            total_ms = (time.monotonic() - start) * 1000
            self._successful_cycles += 1
            return TDDResult(
                success=True,
                phases=phases,
                iterations=iteration,
                final_output=run_output,
                total_duration_ms=total_ms,
            )

        except TDDTestFailureError:
            raise
        except Exception as exc:
            self._failed_cycles += 1
            total_ms = (time.monotonic() - start) * 1000
            raise TDDError(
                f"TDD loop failed: {exc}",
                context={"feature": feature_description},
            ) from exc

    def metrics(self) -> dict[str, Any]:
        return {
            "enabled": self._enabled,
            "degraded": self._degraded,
            "max_iterations": self._max_iterations,
            "total_cycles": self._total_cycles,
            "successful_cycles": self._successful_cycles,
            "failed_cycles": self._failed_cycles,
        }

    async def health_check(self) -> bool:
        return self._enabled and not self._degraded
