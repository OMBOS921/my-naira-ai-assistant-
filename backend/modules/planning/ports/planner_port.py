"""
Abstract port interface for swappable planning strategies.

21_System_Contracts.md §4.2 — Task planner port contract.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from backend.modules.planning._types import TaskPlan


@runtime_checkable
class PlannerPort(Protocol):
    """Abstract port for task decomposition providers."""

    async def decompose(
        self, request: str, context: dict[str, Any] | None = None
    ) -> TaskPlan:
        """Decompose a complex user request into an ordered TaskPlan."""
        ...
