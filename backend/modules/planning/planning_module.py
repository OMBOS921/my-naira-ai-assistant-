"""
PlanningManager — central public manager for the planning engine.

21_System_Contracts.md §4.2 — ModuleInterface protocol.
18_Boot_Sequence.md §2 — Boot sequence.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from backend.modules.planning._executor_bridge import PlanExecutorBridge
from backend.modules.planning._types import PlanResult, TaskPlan
from backend.modules.planning.ports.planner_port import PlannerPort
from backend.modules.planning.providers.rule_based_planner_provider import (
    RuleBasedPlannerProvider,
)

_LOG = logging.getLogger("naira.planning")


class PlanningManager:
    """Central planning manager — breaks complex requests into task graphs before execution.

    Conforms to ``ModuleInterface`` (``backend/types.py``).

    Parameters
    ----------
    config : object | None
        Application configuration.
    logger : logging.Logger | None
        Module-scoped logger.
    event_bus : object | None
        Event bus instance.
    tool_manager : object | None
        ToolManager instance.
    pc_control_manager : object | None
        PCControlManager instance.
    security_manager : object | None
        SecurityManager instance.
    planner_provider : PlannerPort | None
        Swappable decomposition provider (defaults to RuleBasedPlannerProvider).
    """

    _MULTI_STEP_CONNECTIVES = re.compile(
        r"\b(?:and then|then|phir|uske baad|aur|and|after that)\b|,",
        re.IGNORECASE,
    )

    def __init__(
        self,
        *,
        config: object | None = None,
        logger: logging.Logger | None = None,
        event_bus: object | None = None,
        tool_manager: object | None = None,
        pc_control_manager: object | None = None,
        security_manager: object | None = None,
        planner_provider: PlannerPort | None = None,
    ) -> None:
        self._config = config
        self._logger = logger or _LOG
        self._event_bus = event_bus
        self._degraded: bool = False

        self._planner = planner_provider or RuleBasedPlannerProvider()
        self._executor = PlanExecutorBridge(
            tool_manager=tool_manager,
            pc_control_manager=pc_control_manager,
            security_manager=security_manager,
            logger=self._logger,
        )

    # ------------------------------------------------------------------
    # Module lifecycle (ModuleInterface protocol)
    # ------------------------------------------------------------------

    async def async_init(self) -> None:
        """Initialise PlanningManager resources."""
        self._logger.info("PlanningManager initialised")

    async def async_shutdown(self) -> None:
        """Shut down PlanningManager resources."""
        self._degraded = False
        self._logger.info("PlanningManager shut down")

    def degrade(self) -> None:
        """Mark PlanningManager as degraded."""
        self._degraded = True
        self._logger.warning("PlanningManager marked degraded")

    @property
    def degraded(self) -> bool:
        return self._degraded

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_multi_step(self, request: str) -> bool:
        """Cheap heuristic gate to determine if a request contains multiple steps.

        Runs fast with no LLM call.
        """
        if not request or not request.strip():
            return False

        tokens = request.strip().split()
        if len(tokens) <= 2:
            return False

        return bool(self._MULTI_STEP_CONNECTIVES.search(request))

    async def plan(
        self, request: str, context: dict[str, Any] | None = None
    ) -> TaskPlan:
        """Decompose a complex request into a structured TaskPlan."""
        if self._degraded:
            return TaskPlan(steps=[], original_request=request, plan_id="degraded_plan")

        try:
            return await self._planner.decompose(request, context)
        except Exception as exc:
            self._logger.error("Decomposition failed: %s", exc)
            return TaskPlan(steps=[], original_request=request, plan_id="failed_plan")

    async def execute_plan(
        self, plan: TaskPlan, *, confirm_each_step: bool = False
    ) -> PlanResult:
        """Execute a TaskPlan step-by-step."""
        if self._degraded:
            return PlanResult(
                plan_id=plan.plan_id,
                success=False,
                executed_steps=[],
                failed_step=None,
                error="PlanningManager is degraded",
            )

        return await self._executor.execute(plan, confirm_each_step=confirm_each_step)
