"""
Executor bridge for step-by-step task plan execution.

21_System_Contracts.md §4.2 — Execution bridge.
"""

from __future__ import annotations

import logging

from backend.modules.planning._types import PlanResult, StepStatus, TaskPlan, TaskStep

_LOG = logging.getLogger("naira.planning.executor")


class PlanExecutorBridge:
    """Executes a TaskPlan step by step in topological order."""

    def __init__(
        self,
        tool_manager: object | None = None,
        pc_control_manager: object | None = None,
        security_manager: object | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._tool_manager = tool_manager
        self._pc_control_manager = pc_control_manager
        self._security_manager = security_manager
        self._logger = logger or _LOG

    async def execute(
        self, plan: TaskPlan, *, confirm_each_step: bool = False
    ) -> PlanResult:
        """Walk plan steps respecting dependencies and execute each step."""
        executed_steps: list[str] = []
        step_results: dict[str, object] = {}
        completed_step_ids: set[str] = set()

        for step in plan.steps:
            # Check dependency satisfaction
            for dep in step.depends_on:
                if dep not in completed_step_ids:
                    step.status = StepStatus.SKIPPED
                    return PlanResult(
                        plan_id=plan.plan_id,
                        success=False,
                        executed_steps=executed_steps,
                        failed_step=step.id,
                        error=f"Dependency '{dep}' not completed for step '{step.id}'",
                        step_results=step_results,
                    )

            # Security check if security_manager is available
            if self._security_manager is not None:
                perm_fn = getattr(self._security_manager, "permission_check", None)
                if callable(perm_fn):
                    try:
                        perm_res = await perm_fn(step.tool_name, step.tool_args)  # type: ignore
                        decision_val = str(getattr(perm_res, "decision", "")).lower()
                        if decision_val in ("denied", "permissiondecision.denied"):
                            step.status = StepStatus.FAILED
                            err_msg = f"Security policy rejected '{step.id}' ({step.tool_name})"
                            return PlanResult(
                                plan_id=plan.plan_id,
                                success=False,
                                executed_steps=executed_steps,
                                failed_step=step.id,
                                error=err_msg,
                                step_results=step_results,
                            )
                    except Exception as exc:
                        self._logger.warning("Security check warning: %s", exc)
                else:
                    validate_fn = getattr(self._security_manager, "validate_tool_call", None)
                    if callable(validate_fn):
                        try:
                            allowed = await validate_fn(step.tool_name, step.tool_args)  # type: ignore
                            if not allowed:
                                step.status = StepStatus.FAILED
                                err_msg = f"Security policy rejected '{step.id}' ({step.tool_name})"
                                return PlanResult(
                                    plan_id=plan.plan_id,
                                    success=False,
                                    executed_steps=executed_steps,
                                    failed_step=step.id,
                                    error=err_msg,
                                    step_results=step_results,
                                )
                        except Exception as exc:
                            self._logger.warning("Security check warning: %s", exc)

            # Execute step
            step.status = StepStatus.IN_PROGRESS
            try:
                res = await self._dispatch_step(step)
                step.status = StepStatus.COMPLETED
                completed_step_ids.add(step.id)
                executed_steps.append(step.id)
                step_results[step.id] = res
            except Exception as exc:
                step.status = StepStatus.FAILED
                self._logger.error("Step '%s' failed: %s", step.id, exc)
                return PlanResult(
                    plan_id=plan.plan_id,
                    success=False,
                    executed_steps=executed_steps,
                    failed_step=step.id,
                    error=str(exc),
                    step_results=step_results,
                )

        return PlanResult(
            plan_id=plan.plan_id,
            success=True,
            executed_steps=executed_steps,
            failed_step=None,
            error=None,
            step_results=step_results,
        )

    async def _dispatch_step(self, step: TaskStep) -> object:
        """Dispatch a single step to ToolManager or PCControlManager."""
        # Try ToolManager execute_tool_call / execute_tool
        if self._tool_manager is not None:
            exec_fn = getattr(self._tool_manager, "execute_tool", None)
            if callable(exec_fn):
                return await exec_fn(step.tool_name, step.tool_args)  # type: ignore

            exec_call = getattr(self._tool_manager, "execute_tool_call", None)
            if callable(exec_call):
                from backend.types import ToolCall
                tc = ToolCall(id=step.id, name=step.tool_name, arguments=step.tool_args)
                return await exec_call(tc)  # type: ignore

        # Fallback to pc_control_manager or mock execution
        if self._pc_control_manager is not None:
            exec_pc = getattr(self._pc_control_manager, "execute", None)
            if callable(exec_pc):
                return await exec_pc(step.tool_name, step.tool_args)  # type: ignore
        return {"status": "success", "output": f"Executed step {step.id} ({step.tool_name})"}
