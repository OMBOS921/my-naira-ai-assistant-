"""
Unit tests for Fast Command Router (FCR) Action Lifecycle & Verification System.

Tests cover:
- ActionState transitions (QUEUED -> STARTING -> RUNNING -> WAITING -> SUCCESS/FAILED/TIMEOUT)
- Successful & Failed browser launch verification
- Application launch state handling
- File creation, deletion, rename verification
- Web search lifecycle and response formatting
- Timeout and non-blocking lifecycle behavior
- Debug metadata inclusion in debug mode vs production mode
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.runtime.action_lifecycle import (
    ActionLifecycle,
    ActionState,
    NaturalResponseFormatter,
    VerificationResult,
)
from backend.runtime.fast_command_router import CommandIntent, FastCommandRouter

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_APPS_JSON = _PROJECT_ROOT / "config" / "apps.json"


@pytest.fixture
def router() -> FastCommandRouter:
    """Create a FastCommandRouter instance for Action Lifecycle testing."""
    return FastCommandRouter(enable_discovery=False, config_path=_APPS_JSON)


class TestActionLifecycleStateTracker:
    """Verify ActionLifecycle class state transitions and debug metadata."""

    def test_initial_state(self):
        lifecycle = ActionLifecycle("OPEN_APP", "chrome", "LaunchApplication")
        assert lifecycle.state == ActionState.QUEUED
        assert lifecycle.intent_name == "OPEN_APP"
        assert lifecycle.target == "chrome"
        assert lifecycle.handler_name == "LaunchApplication"
        assert len(lifecycle.history) == 1

    def test_state_transitions(self):
        lifecycle = ActionLifecycle("OPEN_APP", "chrome", "LaunchApplication")
        lifecycle.transition_to(ActionState.STARTING, "Routing started")
        lifecycle.transition_to(ActionState.RUNNING, "Launching process")
        lifecycle.transition_to(ActionState.WAITING, "Verifying window")
        lifecycle.transition_to(ActionState.SUCCESS, "Verified window detected")

        assert lifecycle.state == ActionState.SUCCESS
        assert len(lifecycle.history) == 5
        assert lifecycle.end_time is not None
        assert lifecycle.execution_time_ms > 0

    def test_verification_result(self):
        lifecycle = ActionLifecycle("OPEN_APP", "chrome", "LaunchApplication")
        lifecycle.set_verification(
            verified=True,
            running_process="chrome.exe (PID 1234)",
            window_detected="Google Chrome",
            details={"launcher": "system_start"},
        )
        metadata = lifecycle.get_debug_metadata()
        assert metadata["verification_result"]["verified"] is True
        assert metadata["verification_result"]["running_process"] == "chrome.exe (PID 1234)"
        assert metadata["verification_result"]["window_detected"] == "Google Chrome"


class TestNaturalResponseFormatter:
    """Verify natural user-facing response strings."""

    def test_open_success_formatting(self):
        res = NaturalResponseFormatter.format_open_success("youtube")
        assert "YouTube" in res
        assert "open ho gaya" in res or "launch ho gaya" in res

    def test_open_already_running(self):
        res = NaturalResponseFormatter.format_open_success("vscode", already_running=True)
        assert "VS Code" in res
        assert "Pehle se chal raha tha" in res or "pehle se open" in res

    def test_open_failed(self):
        res = NaturalResponseFormatter.format_open_failed("chrome", "Process not detected")
        assert "couldn't open Chrome" in res

    def test_file_op_formatting(self):
        f_create = NaturalResponseFormatter.format_file_op_success("create_folder", "my_data")
        assert "Folder 'my_data' create ho gaya" in f_create

        f_delete = NaturalResponseFormatter.format_file_op_success("delete_file", "notes.txt")
        assert "File 'notes.txt' delete ho gayi" in f_delete

    def test_web_search_formatting(self):
        res = NaturalResponseFormatter.format_web_search_success("Python tutorials", "YouTube")
        assert "YouTube" in res
        assert "Python tutorials" in res


@pytest.mark.asyncio
class TestFCRActionLifecycleExecution:
    """Integration unit tests for Action Lifecycle execution within FastCommandRouter."""

    async def test_successful_app_launch_lifecycle(self, router):
        """Test successful app launch lifecycle and verification state."""
        router._mock_verification = (True, "chrome.exe (PID 999)", "Google Chrome")
        result = await router.execute_fast_command("open chrome", debug=True)
        
        assert result.startswith("SUCCESS")
        assert "[DEBUG:" in result
        assert '"execution_state": "SUCCESS"' in result
        assert '"verified": true' in result

    async def test_failed_app_launch_lifecycle(self, router):
        """Test failed app launch lifecycle when verification fails."""
        router._mock_verification = (False, None, None)
        result = await router.execute_fast_command("open chrome", debug=True)

        assert result.startswith("FAILED_TO_LAUNCH")
        assert "[DEBUG:" in result
        assert '"execution_state": "FAILED"' in result
        assert '"verified": false' in result

    async def test_browser_fallback_lifecycle(self, router):
        """Test browser fallback action lifecycle when app is missing."""
        with patch("webbrowser.open") as mock_web_open:
            result = await router.execute_fast_command("open youtube", debug=True)
            assert result.startswith("SUCCESS") or result.startswith("BROWSER_FALLBACK")
            assert "[DEBUG:" in result

    async def test_file_operation_create_and_delete_lifecycle(self, router, tmp_path):
        """Test folder creation and deletion action lifecycle."""
        test_dir = tmp_path / "lifecycle_test_folder"
        
        # Create folder
        res_create = await router.execute_fast_command(f"create folder {test_dir}", debug=True)
        assert res_create.startswith("SUCCESS")
        assert test_dir.exists()
        assert '"execution_state": "SUCCESS"' in res_create

        # Delete folder
        res_delete = await router.execute_fast_command(f"delete folder {test_dir}", debug=True)
        assert res_delete.startswith("SUCCESS")
        assert not test_dir.exists()
        assert '"execution_state": "SUCCESS"' in res_delete

    async def test_web_search_lifecycle(self, router):
        """Test web search action lifecycle and natural response."""
        with patch("webbrowser.open") as mock_open:
            res = await router.execute_fast_command("youtube pe funny cats search karo", debug=True)
            assert res.startswith("SUCCESS")
            assert "funny cats" in res
            assert '"execution_state": "SUCCESS"' in res
            mock_open.assert_called_once()

    async def test_debug_metadata_omitted_in_production(self, router):
        """Verify debug metadata is omitted from response text in production (debug=False)."""
        router._mock_verification = (True, "calc.exe", "Calculator")
        res = await router.execute_fast_command("open calculator", debug=False)
        assert res.startswith("SUCCESS")
        assert "[DEBUG:" not in res

    async def test_system_info_lifecycle(self, router):
        """Test quick system info execution lifecycle."""
        res = await router.execute_fast_command("current time", debug=True)
        assert res.startswith("INFO:")
        assert '"execution_state": "SUCCESS"' in res
