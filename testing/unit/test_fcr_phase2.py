"""
Unit tests for Fast Command Router Phase 2 Production Hardening.

Coverage requirement checklist:
- Installed app
- Missing app
- Browser fallback
- Failed launch
- Verification success
- Verification failure
- Return codes (SUCCESS, FAILED_TO_LAUNCH, NOT_INSTALLED, BROWSER_FALLBACK, INVALID_TARGET)
- Multilingual & Alias engine compatibility
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import patch
import pytest

from backend.runtime.fast_command_router import FastCommandRouter, CommandIntent


@pytest.fixture
def fcr_instance():
    """Create a FastCommandRouter instance for testing."""
    return FastCommandRouter(enable_discovery=True)


@pytest.mark.asyncio
async def test_return_codes_constant_mapping(fcr_instance):
    """Verify that execution return codes match specification."""
    # Installed app execution -> SUCCESS or BROWSER_FALLBACK or FAILED_TO_LAUNCH
    fcr_instance._mock_verification = (True, "calc.exe (PID 100)", "Calculator")
    res_success = await fcr_instance.execute_fast_command("open calculator")
    assert res_success.startswith("SUCCESS")

    fcr_instance._mock_verification = (False, None, None)
    res_failed = await fcr_instance.execute_fast_command("open calculator")
    assert res_failed.startswith("FAILED_TO_LAUNCH")


@pytest.mark.asyncio
async def test_verification_success_logging(caplog, fcr_instance):
    """Verify launch verification success and corresponding [FCR] logging."""
    caplog.set_level(logging.INFO)
    fcr_instance._mock_verification = (True, "notepad.exe (PID 4321)", "Untitled - Notepad")

    res = await fcr_instance.execute_fast_command("open notepad")
    assert res.startswith("SUCCESS")
    assert "Launch Verification=True" in caplog.text
    assert "RunningProcess=notepad.exe (PID 4321)" in caplog.text
    assert "WindowDetected=Untitled - Notepad" in caplog.text


@pytest.mark.asyncio
async def test_verification_failure_logging(caplog, fcr_instance):
    """Verify launch verification failure returns FAILED_TO_LAUNCH and logs False."""
    caplog.set_level(logging.INFO)
    fcr_instance._mock_verification = (False, None, None)

    res = await fcr_instance.execute_fast_command("open calculator")
    assert res.startswith("FAILED_TO_LAUNCH")
    assert "Launch Verification=False" in caplog.text


@pytest.mark.asyncio
async def test_missing_app_without_fallback(caplog, fcr_instance):
    """Verify missing application with no fallback returns NOT_INSTALLED and logs correctly."""
    caplog.set_level(logging.INFO)
    if fcr_instance.discovery_engine:
        fcr_instance.discovery_engine.discovered_apps.pop("unknown_custom_app_123", None)

    # Alias candidate that has no browser fallback
    with patch.object(fcr_instance.alias_engine, "resolve", return_value="unknown_custom_app_123"), \
         patch.object(fcr_instance.alias_engine, "resolve_key", return_value="unknown_custom_app_123"), \
         patch.object(fcr_instance, "get_browser_fallback", return_value=None):

        res = await fcr_instance.execute_fast_command("open unknown_custom_app_123")
        assert res.startswith("NOT_INSTALLED")
        assert "Reason=NOT_INSTALLED" in caplog.text


@pytest.mark.asyncio
async def test_browser_fallbacks(caplog, fcr_instance):
    """Verify all 11 required browser fallback applications when NOT_INSTALLED."""
    caplog.set_level(logging.INFO)

    fallback_test_cases = [
        ("outlook", "https://outlook.live.com/"),
        ("whatsapp", "https://web.whatsapp.com/"),
        ("youtube", "https://youtube.com/"),
        ("gmail", "https://mail.google.com/"),
        ("github", "https://github.com/"),
        ("google", "https://google.com/"),
        ("chatgpt", "https://chatgpt.com/"),
        ("discord", "https://discord.com/app"),
        ("telegram", "https://web.telegram.org/"),
        ("spotify", "https://open.spotify.com/"),
        ("teams", "https://teams.microsoft.com/"),
    ]

    with patch("webbrowser.open") as mock_web_open:
        for app_name, expected_url in fallback_test_cases:
            caplog.clear()

            # Ensure app is marked NOT_INSTALLED
            if fcr_instance.discovery_engine and app_name in fcr_instance.discovery_engine.discovered_apps:
                del fcr_instance.discovery_engine.discovered_apps[app_name]

            with patch.object(fcr_instance.alias_engine, "resolve_key", return_value=app_name), \
                 patch.object(fcr_instance.alias_engine, "resolve", return_value=app_name), \
                 patch.object(fcr_instance.discovery_engine, "is_installed", return_value=False) if fcr_instance.discovery_engine else patch("shutil.which", return_value=None), \
                 patch("shutil.which", return_value=None):

                res = await fcr_instance.execute_fast_command(f"open {app_name}")

                assert res.startswith("BROWSER_FALLBACK"), f"Expected BROWSER_FALLBACK for {app_name}, got: {res}"
                assert expected_url in res
                mock_web_open.assert_called_with(expected_url)

                # Verify Requirement 3 logging output
                assert "Fallback=True" in caplog.text
                assert f"FallbackURL={expected_url}" in caplog.text
                assert "Reason=NOT_INSTALLED" in caplog.text


@pytest.mark.asyncio
async def test_invalid_target(fcr_instance):
    """Verify INVALID_TARGET return code for non-existent filesystem targets or invalid parameters."""
    res = await fcr_instance.execute_fast_command("delete folder nonexistent_dir_99999")
    assert res.startswith("INVALID_TARGET")

    res = await fcr_instance.execute_fast_command("delete file nonexistent_file_99999.txt")
    assert res.startswith("INVALID_TARGET")


@pytest.mark.asyncio
async def test_multilingual_and_existing_behavior(fcr_instance):
    """Verify Hindi, Hinglish, and English intents are preserved."""
    fcr_instance._mock_verification = (True, "calc.exe", "Calculator")

    # English
    assert fcr_instance.is_fast_command("open calculator")
    res = await fcr_instance.execute_fast_command("open calculator")
    assert res.startswith("SUCCESS")

    # Hinglish
    assert fcr_instance.is_fast_command("calculator kholo")
    res = await fcr_instance.execute_fast_command("calculator kholo")
    assert res.startswith("SUCCESS")

    # Hindi (Devanagari)
    assert fcr_instance.is_fast_command("कैलकुलेटर खोलो")
    res = await fcr_instance.execute_fast_command("कैलकुलेटर खोलो")
    assert res.startswith("SUCCESS")


@pytest.mark.asyncio
async def test_phase23_fuzzy_matching(fcr_instance):
    """Verify production fuzzy matching for common typos (BUG 3)."""
    assert fcr_instance.alias_engine.resolve("vs coad") == "code"
    assert fcr_instance.alias_engine.resolve("vs cod") == "code"
    assert fcr_instance.alias_engine.resolve("calclator") == "calc"
    assert fcr_instance.alias_engine.resolve("explorrer") == "explorer"
    assert fcr_instance.alias_engine.resolve("spotfy") == "spotify"
    assert fcr_instance.alias_engine.resolve("yutube") == "https://youtube.com"
    assert fcr_instance.alias_engine.resolve("powrshell") == "powershell"
    assert fcr_instance.alias_engine.resolve("cmdd") == "cmd"


@pytest.mark.asyncio
async def test_phase23_unknown_targets(fcr_instance):
    """Verify unknown targets return INVALID_TARGET without launch or fallback (BUG 4)."""
    for cmd in ["banana kholo", "television kholo", "abcd kholo", "xyz kholo"]:
        res = await fcr_instance.execute_fast_command(cmd)
        assert res.startswith("INVALID_TARGET"), f"Expected INVALID_TARGET for '{cmd}', got: {res}"


@pytest.mark.asyncio
async def test_phase23_builtin_cli_apps(fcr_instance):
    """Verify built-in CLI apps (cmd, powershell) always open directly (BUG 6)."""
    fcr_instance._mock_verification = (True, "cmd.exe (PID 123)", "Command Prompt")
    res_cmd = await fcr_instance.execute_fast_command("cmd kholo")
    assert res_cmd.startswith("SUCCESS")

    fcr_instance._mock_verification = (True, "powershell.exe (PID 456)", "Windows PowerShell")
    res_ps = await fcr_instance.execute_fast_command("powershell kholo")
    assert res_ps.startswith("SUCCESS")

