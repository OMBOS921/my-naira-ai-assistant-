"""
Rule-based Task Planner Provider — Phase-1 decomposition strategy.

21_System_Contracts.md §4.2 — Task planner port implementation.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from backend.modules.planning._types import StepStatus, TaskPlan, TaskStep
from backend.runtime.fast_command_router import (
    MultilingualNormalizer,
    WakeWordCleaner,
)


class RuleBasedPlannerProvider:
    """Decomposes compound multi-step requests into an ordered TaskPlan using pattern matching.

    Reuses ``WakeWordCleaner`` and ``MultilingualNormalizer`` from ``fast_command_router``.
    """

    _CONNECTIVES_RE = re.compile(
        r"\s+(?:and then|then|phir|uske baad|aur|and|,)\s+",
        re.IGNORECASE,
    )

    async def decompose(
        self, request: str, context: dict[str, Any] | None = None
    ) -> TaskPlan:
        """Decompose a request string into ordered TaskSteps."""
        cleaned = WakeWordCleaner.clean(request)
        if not cleaned:
            cleaned = request

        # Split request into distinct sub-clause intent strings
        raw_parts = self._CONNECTIVES_RE.split(cleaned)
        sub_clauses = [p.strip() for p in raw_parts if p.strip()]

        if not sub_clauses:
            sub_clauses = [request.strip()]

        steps: list[TaskStep] = []
        prev_step_id: str | None = None

        for idx, clause in enumerate(sub_clauses, start=1):
            step_id = f"step_{idx}_{uuid.uuid4().hex[:6]}"
            depends_on = [prev_step_id] if prev_step_id else []

            tool_name, tool_args = self._infer_tool(clause)
            step = TaskStep(
                id=step_id,
                description=f"Execute: {clause}",
                tool_name=tool_name,
                tool_args=tool_args,
                depends_on=depends_on,
                status=StepStatus.PENDING,
            )
            steps.append(step)
            prev_step_id = step_id

        plan_id = f"plan_{uuid.uuid4().hex[:8]}"
        return TaskPlan(steps=steps, original_request=request, plan_id=plan_id)

    def _infer_tool(self, clause: str) -> tuple[str, dict[str, Any]]:
        """Infer tool name and arguments from a normalized clause."""
        tokens = clause.split()
        if not tokens:
            return "pc_control", {"action": "raw_command", "command": clause}

        first_token = tokens[0].lower()
        norm_verb = MultilingualNormalizer.normalize_token(first_token)

        if norm_verb == "open":
            target = " ".join(tokens[1:]).strip() if len(tokens) > 1 else clause
            return "open_application", {"target": target}
        elif norm_verb == "lock":
            return "lock_workstation", {}
        elif norm_verb == "shutdown":
            return "shutdown_system", {}
        elif norm_verb == "restart":
            return "restart_system", {}
        elif norm_verb == "volume":
            return "set_volume", {"target": clause}
        elif norm_verb == "create":
            target = " ".join(tokens[1:]).strip()
            return "create_file_or_folder", {"target": target}
        elif norm_verb == "delete":
            target = " ".join(tokens[1:]).strip()
            return "delete_file_or_folder", {"target": target}

        return "execute_command", {"command": clause}
