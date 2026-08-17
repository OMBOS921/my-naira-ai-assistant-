"""
Unit tests for DecisionManager.

pytest + pytest-asyncio, marked unit.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.modules.analytics import (
    AnalyticsEvent,
    AnalyticsManager,
    EventType,
)
from backend.modules.decision import (
    DecisionManager,
    RouteDecision,
    RouteTarget,
)
from backend.modules.planning import PlanningManager


class DummyFastCommandRouter:
    """Mock FastCommandRouter for testing routing logic."""

    def is_fast_command(self, request: str) -> bool:
        return request.lower() in ("open chrome", "lock pc", "flaky command")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_decision_happy_path() -> None:
    """Test standard decision routing for fast commands, planning, and conversation."""
    fcr = DummyFastCommandRouter()
    planning_mgr = PlanningManager()
    decision_mgr = DecisionManager(
        fast_command_router=fcr,
        planning_manager=planning_mgr,
    )
    await decision_mgr.async_init()

    # Fast command route
    dec: RouteDecision = await decision_mgr.decide("open chrome")
    assert dec.target == RouteTarget.FAST_COMMAND_ROUTER

    # Planning route
    dec = await decision_mgr.decide("open chrome and then lock pc")
    assert dec.target == RouteTarget.PLANNING_ENGINE

    # Coding route
    dec = await decision_mgr.decide("refactor this python function")
    assert dec.target == RouteTarget.CODING_AGENT

    # Default LLM route
    dec = await decision_mgr.decide("what is the capital of France?")
    assert dec.target == RouteTarget.UNHANDLED

    # Complex prompt containing script execution, error debugging, and execute_local_python tool call
    complex_prompt = (
        "Write a script with a NameError, run it via execute_local_python, "
        "read the error, fix it, and run again"
    )
    dec = await decision_mgr.decide(complex_prompt)
    assert dec.target == RouteTarget.CODING_AGENT
    assert dec.target != RouteTarget.FAST_COMMAND_ROUTER


@pytest.mark.unit
@pytest.mark.asyncio
async def test_decision_degraded_path() -> None:
    """Test degraded decision manager returns safe fallback."""
    decision_mgr = DecisionManager()
    decision_mgr.degrade()
    assert decision_mgr.degraded

    dec = await decision_mgr.decide("open chrome")
    assert dec.target == RouteTarget.UNHANDLED
    assert dec.confidence == 1.0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_decision_route_demotion_via_analytics(tmp_path: Path) -> None:
    """Test that DecisionManager demotes a route after AnalyticsManager reports low success rate."""
    db_file = tmp_path / "analytics_demote.db"
    analytics_mgr = AnalyticsManager(db_path=db_file)
    await analytics_mgr.async_init()

    fcr = DummyFastCommandRouter()
    decision_mgr = DecisionManager(
        analytics=analytics_mgr,
        fast_command_router=fcr,
    )
    await decision_mgr.async_init()

    # Initially high/unknown success rate -> FCR route chosen
    dec = await decision_mgr.decide("flaky command")
    assert dec.target == RouteTarget.FAST_COMMAND_ROUTER

    # Record multiple failure events for this intent pattern
    for _ in range(5):
        analytics_mgr.record(
            AnalyticsEvent(
                event_type=EventType.COMMAND_FAILURE,
                payload={"intent": "flaky command"},
                success=False,
            )
        )

    # Now decision manager should demote the route from FCR to UNHANDLED
    dec_after = await decision_mgr.decide("flaky command")
    assert dec_after.target == RouteTarget.UNHANDLED
    assert "demoted" in dec_after.reason.lower()

    await analytics_mgr.async_shutdown()
