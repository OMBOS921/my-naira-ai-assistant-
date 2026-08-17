from typing import Any
"""Unit tests for OS action verification, fake success fixes, and response formatting in Naira OS."""

import os
import shutil
import tempfile
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from backend.runtime.fast_command_router import FastCommandRouter, CommandIntent
from backend.runtime.action_lifecycle import ActionLifecycle, ActionState, NaturalResponseFormatter
from backend.runtime._runtime_manager import RuntimeManager
from backend.modules.coding_agent.providers.vscode_integration_provider import VSCodeIntegrationProvider
from backend.types import Message, UserRequest, UserResponse
@pytest.fixture
def temp_workspace():
    tmp_dir = tempfile.mkdtemp()
    yield Path(tmp_dir)
    shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.fixture
def router():
    return FastCommandRouter(enable_discovery=False)


# ----------------------------------------------------------------------
# 1. Real Success Tests
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_folder_creation_real_success(router, temp_workspace):
    folder_target = str(temp_workspace / "test_folder_success")
    res = await router.execute_fast_command(f"create folder {folder_target}")
    assert "SUCCESS" in res
    assert Path(folder_target).exists()
    assert Path(folder_target).is_dir()


@pytest.mark.asyncio
async def test_file_creation_real_success(router, temp_workspace):
    file_target = str(temp_workspace / "test_file_success.txt")
    res = await router.execute_fast_command(f"create file {file_target}")
    assert "SUCCESS" in res
    assert Path(file_target).exists()
    assert Path(file_target).is_file()


@pytest.mark.asyncio
async def test_file_opening_real_success(router, temp_workspace):
    file_target = str(temp_workspace / "test_open_file.txt")
    Path(file_target).write_text("hello world", encoding="utf-8")
    
    with patch.object(router, "_verify_launch", new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = (True, "notepad.exe (PID 1234)", "test_open_file.txt - Notepad")
        res = await router.execute_fast_command(f"open file {file_target}")
        assert "SUCCESS" in res
        assert "open ho gayi" in res or "Opened" in res


@pytest.mark.asyncio
async def test_app_launch_real_success(router):
    router._mock_verification = (True, "calc.exe (PID 9999)", "Calculator")
    res = await router.execute_fast_command("open calculator")
    assert "SUCCESS" in res


@pytest.mark.asyncio
async def test_browser_open_real_success(router):
    with patch("webbrowser.open", return_value=True), \
         patch.object(router, "_verify_launch", new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = (True, "chrome.exe (PID 4321)", "Google Chrome")
        res = await router.execute_fast_command("open https://google.com")
        assert "SUCCESS" in res


@pytest.mark.asyncio
async def test_vscode_launch_real_success(temp_workspace):
    file_path = str(temp_workspace / "test_code.py")
    Path(file_path).write_text("print('test')", encoding="utf-8")
    
    provider = VSCodeIntegrationProvider()
    with patch.object(VSCodeIntegrationProvider, "is_available", new_callable=PropertyMock, return_value=True), \
         patch("subprocess.run") as mock_sub, \
         patch("psutil.process_iter") as mock_ps:
        mock_sub.return_value = MagicMock(returncode=0, stderr="")
        proc_mock = MagicMock()
        proc_mock.info = {"name": "Code.exe"}
        mock_ps.return_value = [proc_mock]
        
        res = await provider.open_file(file_path)
        assert res["success"] is True
        assert res["error"] is None


# ----------------------------------------------------------------------
# 2. Total Failure Tests
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_file_opening_total_failure_nonexistent(router, temp_workspace):
    nonexistent = str(temp_workspace / "ghost_file.txt")
    res = await router.execute_fast_command(f"open file {nonexistent}")
    assert "INVALID_TARGET" in res or "does not exist" in res
    assert "SUCCESS" not in res


@pytest.mark.asyncio
async def test_app_launch_total_failure_unverified(router):
    with patch.object(router, "_check_if_running", new_callable=AsyncMock) as mock_check, \
         patch.object(router, "_verify_launch", new_callable=AsyncMock) as mock_verify:
        mock_check.return_value = (False, None, None)
        mock_verify.return_value = (False, None, None)
        res = await router.execute_fast_command("open calc")
        assert "FAILED_TO_LAUNCH" in res
        assert "SUCCESS" not in res


@pytest.mark.asyncio
async def test_browser_open_total_failure_unverified(router):
    with patch("webbrowser.open", return_value=True), \
         patch.object(router, "_check_if_running", new_callable=AsyncMock) as mock_check, \
         patch.object(router, "_verify_launch", new_callable=AsyncMock) as mock_verify:
        mock_check.return_value = (False, None, None)
        mock_verify.return_value = (False, None, None)
        res = await router.execute_fast_command("open https://google.com")
        assert "FAILED_TO_LAUNCH" in res
        assert "SUCCESS" not in res


@pytest.mark.asyncio
async def test_folder_creation_failure_on_exception(router):
    with patch("pathlib.Path.mkdir", side_effect=PermissionError("Access denied")):
        res = await router.execute_fast_command("create folder C:\\RestrictedFolder_12345")
        assert "FAILED" in res
        assert "Access denied" in res or "Directory creation failed" in res
        assert "SUCCESS" not in res


# ----------------------------------------------------------------------
# 3. Partial Success & Multi-Step Tests
# ----------------------------------------------------------------------

def test_natural_response_formatter_multi_step():
    res_full = NaturalResponseFormatter.format_multi_step_result(
        step1_name="File Import",
        step1_success=True,
        step2_name="Editor Launch",
        step2_success=True,
    )
    assert "SUCCESS" in res_full

    res_partial = NaturalResponseFormatter.format_multi_step_result(
        step1_name="File Import",
        step1_success=True,
        step2_name="Editor Launch",
        step2_success=False,
        step2_error="Process code.exe not detected",
    )
    assert res_partial.startswith("PARTIAL_SUCCESS:")
    assert "Step 1 (File Import) succeeded" in res_partial
    assert "Step 2 (Editor Launch) failed" in res_partial
    assert not res_partial.startswith("SUCCESS:")


# ----------------------------------------------------------------------
# 4. Provider Outage Fallback & Response Formatting Tests
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_synthesis_preserves_raw_output_on_provider_outage():
    runtime = RuntimeManager()
    runtime._degraded = False

    raw_exec_output = "SUCCESS: Folder 'my_project' create ho gaya."
    user_prompt = "create folder my_project"

    mock_llm = AsyncMock()
    mock_llm.generate.return_value = Any(
        text="I'm having trouble connecting to AI services right now. Please try again in a moment.",
        tool_calls=None,
        finish_reason="stop",
        token_usage=Any(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        provider="orchestrator_outage_fallback",
        duration_ms=0.0,
    )
    runtime._llm_manager = mock_llm

    synthesized = await runtime._synthesize_conversational_reply(user_prompt, raw_exec_output)
    # Must preserve the real execution result, NOT the AI provider outage error
    assert synthesized == raw_exec_output
    assert "trouble connecting" not in synthesized


@pytest.mark.asyncio
async def test_synthesis_does_not_echo_user_command():
    runtime = RuntimeManager()
    raw_exec_output = "SUCCESS: Opened Notepad successfully."
    user_prompt = "open notepad"

    mock_llm = AsyncMock()
    mock_llm.generate.return_value = Any(
        text="open notepad",
        tool_calls=None,
        finish_reason="stop",
        token_usage=Any(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        provider="gemini",
        duration_ms=50.0,
    )
    runtime._llm_manager = mock_llm

    synthesized = await runtime._synthesize_conversational_reply(user_prompt, raw_exec_output)
    # Must return raw_exec_output rather than echoing the user input
    assert synthesized == raw_exec_output


# ----------------------------------------------------------------------
# 5. Malformed Command Handling Tests
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_malformed_command_handling(router):
    res_empty = await router.execute_fast_command("")
    assert "FAILED" in res_empty or "Unrecognized" in res_empty
    assert "SUCCESS" not in res_empty

    res_garbage = await router.execute_fast_command("asdfghjkqwerty123456")
    assert "FAILED" in res_garbage or "INVALID_TARGET" in res_garbage
    assert "SUCCESS" not in res_garbage
