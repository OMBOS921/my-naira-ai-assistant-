from __future__ import annotations

import time
from pathlib import Path

import pytest

from backend.modules.security.permission_engine import (
    PermissionDecision,
    PermissionEngine,
    PermissionResult,
)


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "naira_security_test.db"


@pytest.fixture
def engine(temp_db_path: Path) -> PermissionEngine:
    eng = PermissionEngine(db_path=temp_db_path, session_id="test_session")
    yield eng
    eng.close()


def test_permission_check_speed(engine: PermissionEngine) -> None:
    start = time.perf_counter()
    res = engine.check("fcr_screenshot")
    duration_ms = (time.perf_counter() - start) * 1000
    assert res.decision == PermissionDecision.ALLOWED
    assert duration_ms < 5.0, f"Check took {duration_ms:.2f}ms, expected < 5ms"


def test_permission_check_session_caching(engine: PermissionEngine) -> None:
    res1 = engine.check("fcr_web_search")
    assert res1.decision == PermissionDecision.ALLOWED
    assert res1.cached_from_scope == ""

    res2 = engine.check("fcr_web_search")
    assert res2.decision == PermissionDecision.ALLOWED
    assert res2.cached_from_scope == "session"


def test_permission_grant_permanent(engine: PermissionEngine) -> None:
    engine.grant("fcr_kill_process", PermissionDecision.ALLOWED, scope="permanent", reason="User approved")
    engine.clear_session()

    res = engine.check("fcr_kill_process")
    assert res.decision == PermissionDecision.ALLOWED
    assert res.cached_from_scope == "permanent"


def test_rate_limiting(engine: PermissionEngine) -> None:
    for _ in range(2):
        engine.record_call("pc_power")

    res = engine.check("pc_power", risk_level="critical")
    assert res.decision == PermissionDecision.RATE_LIMITED
    assert "Rate limit exceeded" in res.reason


def test_audit_logging_and_stats(engine: PermissionEngine) -> None:
    engine.log_audit("fcr_web_search", {"query": "test"}, PermissionDecision.ALLOWED, "low", 1.2)
    engine.log_audit("fcr_kill_process", {"pid": 1234}, PermissionDecision.NEEDS_CONFIRMATION, "high", 2.5)

    logs = engine.get_audit_log(limit=10)
    assert len(logs) == 2

    stats = engine.get_stats()
    assert stats["total_operations"] == 2
    assert stats["allowed"] == 1


def test_revoke(engine: PermissionEngine) -> None:
    engine.grant("custom_tool", PermissionDecision.ALLOWED, scope="permanent")
    assert engine._get_permanent_grant("custom_tool") is not None

    revoked = engine.revoke("custom_tool", scope="permanent")
    assert revoked
    assert engine._get_permanent_grant("custom_tool") is None
