"""
Data types and containers for the Planning Engine.

21_System_Contracts.md §4.2 — Planning contracts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class StepStatus(StrEnum):
    """Execution status for an individual plan step."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class TaskStep:
    """Individual step in a decomposed task plan."""

    id: str
    description: str
    tool_name: str
    tool_args: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING


@dataclass
class TaskPlan:
    """Ordered collection of task steps decomposing a user request."""

    steps: list[TaskStep]
    original_request: str
    plan_id: str = ""


@dataclass
class PlanResult:
    """Summary of plan execution result."""

    plan_id: str
    success: bool
    executed_steps: list[str]
    failed_step: str | None = None
    error: str | None = None
    step_results: dict[str, Any] = field(default_factory=dict)
