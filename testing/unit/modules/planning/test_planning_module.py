"""
Unit tests for PlanningManager.

pytest + pytest-asyncio, marked unit.
"""

from __future__ import annotations

import pytest

from backend.modules.planning import (
    PlanningManager,
    PlanResult,
    StepStatus,
    TaskPlan,
)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_planning_is_multi_step() -> None:
    """Test fast multi-step heuristic gate."""
    manager = PlanningManager()
    await manager.async_init()

    assert not manager.is_multi_step("open chrome")
    assert manager.is_multi_step("open chrome and then search python")
    assert manager.is_multi_step("open terminal phir run pytest")
    assert manager.is_multi_step("lock pc, restart system, and shutdown")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_planning_happy_path() -> None:
    """Test decomposing and executing a multi-step task plan."""
    manager = PlanningManager()
    await manager.async_init()

    plan: TaskPlan = await manager.plan("open chrome and then lock pc")
    assert len(plan.steps) == 2
    assert plan.steps[0].tool_name == "open_application"
    assert plan.steps[1].depends_on == [plan.steps[0].id]

    result: PlanResult = await manager.execute_plan(plan)
    assert result.success
    assert len(result.executed_steps) == 2
    assert plan.steps[0].status == StepStatus.COMPLETED
    assert plan.steps[1].status == StepStatus.COMPLETED

    await manager.async_shutdown()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_planning_degraded_path() -> None:
    """Test degraded planning manager safe fallback behavior."""
    manager = PlanningManager()
    manager.degrade()
    assert manager.degraded

    plan = await manager.plan("open chrome and then search google")
    assert len(plan.steps) == 0

    result = await manager.execute_plan(plan)
    assert not result.success
    assert result.error == "PlanningManager is degraded"
