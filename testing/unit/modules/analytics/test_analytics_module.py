"""
Unit tests for AnalyticsManager.

pytest + pytest-asyncio, marked unit.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from backend.modules.analytics import (
    AnalyticsEvent,
    AnalyticsManager,
    AnalyticsSummary,
    EventType,
)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_analytics_happy_path(tmp_path: Path) -> None:
    """Test happy path event recording and aggregate queries."""
    db_file = tmp_path / "test_analytics.db"
    manager = AnalyticsManager(db_path=db_file)

    await manager.async_init()
    assert not manager.degraded

    manager.record(
        AnalyticsEvent(
            event_type=EventType.FCR_HIT,
            timestamp=datetime.now(),
            payload={"intent": "open_app"},
            duration_ms=5.2,
            success=True,
        )
    )
    manager.record(
        AnalyticsEvent(
            event_type=EventType.TOOL_CALL,
            timestamp=datetime.now(),
            payload={"tool_name": "chrome"},
            duration_ms=120.0,
            success=True,
        )
    )

    summary: AnalyticsSummary = manager.get_summary("today")
    assert summary.total_events == 2
    assert summary.success_rate == 1.0
    assert manager.get_fcr_effectiveness() == 1.0

    await manager.async_shutdown()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_analytics_degraded_path(tmp_path: Path) -> None:
    """Test degraded state returns safe defaults without crashing."""
    manager = AnalyticsManager(db_path="/invalid_path/naira_analytics.db")
    # Mark degraded directly
    manager.degrade()
    assert manager.degraded

    # Record should not raise exception
    manager.record(
        AnalyticsEvent(
            event_type=EventType.FCR_HIT,
            success=True,
        )
    )

    summary = manager.get_summary("all")
    assert summary.total_events == 0
    assert summary.success_rate == 0.0
    assert manager.get_fcr_effectiveness() == 0.0
