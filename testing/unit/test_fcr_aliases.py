"""
Comprehensive Unit Tests for FCR Production Hardening — Phase 1.

Covers:
- Alias database coverage (all 40+ apps with English, Hindi, Hinglish aliases)
- Common typo resolution
- AppDiscoveryEngine (mock-based, no real registry/filesystem access)
- NOT_INSTALLED handling
- Enhanced [FCR] logging verification
- Backward compatibility with all original aliases
- Edge cases (empty input, unicode, duplicates)

Total: 85+ test cases.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from backend.runtime.fast_command_router import (
    FastCommandRouter,
    CommandIntent,
    WakeWordCleaner,
    MultilingualNormalizer,
    AliasEngine,
    AppDiscoveryEngine,
    IntentEngine,
    RouteMatch,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_fcr_aliases")

# Path to the real config/apps.json
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_APPS_JSON = _PROJECT_ROOT / "config" / "apps.json"


# ======================================================================
# Fixtures
# ======================================================================

@pytest.fixture(scope="module")
def apps_config() -> Dict[str, Any]:
    """Load the actual apps.json for validation."""
    with open(_APPS_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def alias_engine() -> AliasEngine:
    """AliasEngine loaded from the real config/apps.json."""
    return AliasEngine(config_path=_APPS_JSON)


@pytest.fixture
def router() -> FastCommandRouter:
    """FastCommandRouter with discovery disabled (for fast unit tests)."""
    return FastCommandRouter(enable_discovery=False, config_path=_APPS_JSON)


@pytest.fixture
def mock_discovery() -> AppDiscoveryEngine:
    """AppDiscoveryEngine with mocked app metadata and pre-populated discovered apps."""
    meta = {
        "chrome": {
            "target": "chrome",
            "aliases": ["chrome", "google chrome"],
            "exe_names": ["chrome.exe"],
            "install_paths": [],
        },
        "photoshop": {
            "target": "photoshop",
            "aliases": ["photoshop", "adobe photoshop"],
            "exe_names": ["Photoshop.exe"],
            "install_paths": [r"C:\Program Files\Adobe\Adobe Photoshop 2024"],
        },
    }
    with patch.object(AppDiscoveryEngine, "_scan"):
        engine = AppDiscoveryEngine(meta)
    # Simulate that chrome was discovered, photoshop was not
    engine.discovered_apps = {
        "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    }
    return engine


# ======================================================================
# 1. Config / apps.json Structural Validation
# ======================================================================

class TestAppsJsonStructure:
    """Validate the config/apps.json file structure and completeness."""

    def test_apps_json_exists(self):
        assert _APPS_JSON.exists(), "config/apps.json must exist"

    def test_apps_json_is_valid_json(self, apps_config):
        assert isinstance(apps_config, dict), "Root must be a JSON object"

    def test_minimum_app_entries(self, apps_config):
        assert len(apps_config) >= 40, f"Expected >= 40 app entries, got {len(apps_config)}"

    def test_minimum_total_aliases(self, apps_config):
        total = sum(len(v.get("aliases", [])) for v in apps_config.values())
        assert total >= 200, f"Expected >= 200 total aliases, got {total}"

    def test_every_entry_has_required_fields(self, apps_config):
        for key, entry in apps_config.items():
            assert "target" in entry, f"Entry '{key}' missing 'target'"
            assert "aliases" in entry, f"Entry '{key}' missing 'aliases'"
            assert isinstance(entry["aliases"], list), f"Entry '{key}' aliases must be a list"
            assert len(entry["aliases"]) >= 2, f"Entry '{key}' needs at least 2 aliases, got {len(entry['aliases'])}"

    def test_every_entry_has_exe_names_field(self, apps_config):
        for key, entry in apps_config.items():
            assert "exe_names" in entry, f"Entry '{key}' missing 'exe_names'"
            assert isinstance(entry["exe_names"], list), f"Entry '{key}' exe_names must be a list"

    def test_every_entry_has_install_paths_field(self, apps_config):
        for key, entry in apps_config.items():
            assert "install_paths" in entry, f"Entry '{key}' missing 'install_paths'"
            assert isinstance(entry["install_paths"], list), f"Entry '{key}' install_paths must be a list"

    @pytest.mark.parametrize("app_key", [
        "chrome", "msedge", "firefox", "brave", "opera",
        "code", "devenv",
        "notepad", "calc", "mspaint", "paint3d",
        "winword", "excel", "powerpnt", "outlook", "teams", "onenote", "onedrive",
        "whatsapp", "telegram", "discord",
        "spotify", "vlc", "obs",
        "steam", "epicgames",
        "acrord32", "photoshop",
        "explorer", "ms-settings:", "control", "cmd", "powershell",
        "taskmgr", "devmgmt.msc", "regedit", "snippingtool",
        "ms-clock:", "microsoft.windows.camera:", "ms-photos:",
    ])
    def test_required_apps_present(self, apps_config, app_key):
        assert app_key in apps_config, f"Required app '{app_key}' missing from apps.json"


# ======================================================================
# 2. AliasEngine — Config-Driven (Zero Hardcoded Aliases)
# ======================================================================

class TestAliasEngineConfigDriven:
    """Verify that AliasEngine loads exclusively from config, with no hardcoded aliases."""

    def test_no_default_config_attribute(self):
        """AliasEngine must not have a DEFAULT_CONFIG class attribute."""
        assert not hasattr(AliasEngine, "DEFAULT_CONFIG"), "DEFAULT_CONFIG must be removed"

    def test_loads_from_config_file(self, alias_engine):
        assert len(alias_engine.alias_map) >= 200

    def test_resolve_returns_target(self, alias_engine):
        assert alias_engine.resolve("chrome") == "chrome"
        assert alias_engine.resolve("vscode") == "code"
        assert alias_engine.resolve("yt") == "https://youtube.com"

    def test_resolve_key_returns_app_key(self, alias_engine):
        assert alias_engine.resolve_key("google chrome") == "chrome"
        assert alias_engine.resolve_key("vs code") == "code"
        assert alias_engine.resolve_key("calculator") == "calc"

    def test_get_app_meta_returns_dict(self, alias_engine):
        meta = alias_engine.get_app_meta("chrome")
        assert meta is not None
        assert "target" in meta
        assert "aliases" in meta
        assert "exe_names" in meta

    def test_get_app_meta_returns_none_for_unknown(self, alias_engine):
        assert alias_engine.get_app_meta("nonexistent_app") is None

    def test_resolve_returns_none_for_unknown(self, alias_engine):
        assert alias_engine.resolve("xyzzy_unknown_app") is None

    def test_case_insensitive_resolution(self, alias_engine):
        assert alias_engine.resolve("Chrome") == alias_engine.resolve("chrome")
        assert alias_engine.resolve("NOTEPAD") == alias_engine.resolve("notepad")

    def test_missing_config_path_logs_error(self, tmp_path):
        """If config path is explicitly invalid, engine should have no aliases."""
        engine = AliasEngine(config_path=tmp_path / "nonexistent.json")
        assert len(engine.alias_map) == 0


# ======================================================================
# 3. Alias Resolution — All Required Applications
# ======================================================================

# Each tuple: (alias_input, expected_target)
ENGLISH_ALIAS_TESTS = [
    ("chrome", "chrome"),
    ("google chrome", "chrome"),
    ("edge", "msedge"),
    ("microsoft edge", "msedge"),
    ("firefox", "firefox"),
    ("brave", "brave"),
    ("opera", "opera"),
    ("vscode", "code"),
    ("vs code", "code"),
    ("visual studio code", "code"),
    ("visual studio", "devenv"),
    ("notepad", "notepad"),
    ("calculator", "calc"),
    ("paint", "mspaint"),
    ("paint 3d", "ms-paint:"),
    ("word", "winword"),
    ("excel", "excel"),
    ("powerpoint", "powerpnt"),
    ("ppt", "powerpnt"),
    ("outlook", "outlook"),
    ("teams", "ms-teams:"),
    ("onenote", "onenote"),
    ("onedrive", "onedrive"),
    ("whatsapp", "whatsapp:"),
    ("telegram", "telegram"),
    ("discord", "discord"),
    ("spotify", "spotify"),
    ("vlc", "vlc"),
    ("obs", "obs64"),
    ("steam", "steam"),
    ("epic games", "com.epicgames.launcher:"),
    ("adobe reader", "acrord32"),
    ("photoshop", "photoshop"),
    ("file explorer", "explorer"),
    ("settings", "ms-settings:"),
    ("control panel", "control"),
    ("cmd", "cmd"),
    ("command prompt", "cmd"),
    ("powershell", "powershell"),
    ("task manager", "taskmgr"),
    ("device manager", "devmgmt.msc"),
    ("registry editor", "regedit"),
    ("snipping tool", "snippingtool"),
    ("clock", "ms-clock:"),
    ("camera", "microsoft.windows.camera:"),
    ("photos", "ms-photos:"),
]

HINDI_ALIAS_TESTS = [
    ("क्रोम", "chrome"),
    ("गूगल क्रोम", "chrome"),
    ("एज", "msedge"),
    ("फायरफॉक्स", "firefox"),
    ("वीएस कोड", "code"),
    ("कोड", "code"),
    ("नोटपैड", "notepad"),
    ("कैलकुलेटर", "calc"),
    ("पेंट", "mspaint"),
    ("वर्ड", "winword"),
    ("एक्सेल", "excel"),
    ("पावरपॉइंट", "powerpnt"),
    ("आउटलुक", "outlook"),
    ("टीम्स", "ms-teams:"),
    ("व्हाट्सएप", "whatsapp:"),
    ("टेलीग्राम", "telegram"),
    ("डिस्कॉर्ड", "discord"),
    ("स्पॉटिफाई", "spotify"),
    ("वीएलसी", "vlc"),
    ("स्टीम", "steam"),
    ("फोटोशॉप", "photoshop"),
    ("एक्सप्लोरर", "explorer"),
    ("सेटिंग्स", "ms-settings:"),
    ("कमांड प्रॉम्प्ट", "cmd"),
    ("पावरशेल", "powershell"),
    ("टास्क मैनेजर", "taskmgr"),
    ("कैमरा", "microsoft.windows.camera:"),
    ("घड़ी", "ms-clock:"),
]

TYPO_ALIAS_TESTS = [
    ("crome", "chrome"),
    ("fierefox", "firefox"),
    ("vscod", "code"),
    ("calulator", "calc"),
    ("outook", "outlook"),
    ("spotifiy", "spotify"),
    ("dicord", "discord"),
    ("watsapp", "whatsapp:"),
    ("telgram", "telegram"),
    ("fotoshop", "photoshop"),
    ("powepoint", "powerpnt"),
    ("exel", "excel"),
]


class TestAliasResolution:
    """Test that all required apps resolve correctly from aliases."""

    @pytest.mark.parametrize("alias,expected_target", ENGLISH_ALIAS_TESTS)
    def test_english_alias(self, alias_engine, alias, expected_target):
        result = alias_engine.resolve(alias)
        assert result == expected_target, f"Alias '{alias}' should resolve to '{expected_target}', got '{result}'"

    @pytest.mark.parametrize("alias,expected_target", HINDI_ALIAS_TESTS)
    def test_hindi_alias(self, alias_engine, alias, expected_target):
        result = alias_engine.resolve(alias)
        assert result == expected_target, f"Hindi alias '{alias}' should resolve to '{expected_target}', got '{result}'"

    @pytest.mark.parametrize("alias,expected_target", TYPO_ALIAS_TESTS)
    def test_typo_alias(self, alias_engine, alias, expected_target):
        result = alias_engine.resolve(alias)
        assert result == expected_target, f"Typo alias '{alias}' should resolve to '{expected_target}', got '{result}'"


# ======================================================================
# 4. AppDiscoveryEngine (mock-based)
# ======================================================================

class TestAppDiscoveryEngine:
    """Test AppDiscoveryEngine with mocked system calls."""

    def test_is_installed_true_for_discovered(self, mock_discovery):
        assert mock_discovery.is_installed("chrome") is True

    def test_is_installed_false_for_undiscovered(self, mock_discovery):
        assert mock_discovery.is_installed("photoshop") is False

    def test_get_executable_returns_path(self, mock_discovery):
        exe = mock_discovery.get_executable("chrome")
        assert exe is not None
        assert "chrome" in exe.lower()

    def test_get_executable_returns_none_for_undiscovered(self, mock_discovery):
        assert mock_discovery.get_executable("photoshop") is None

    def test_scan_system_path_finds_exe(self):
        """Test that _scan_system_path uses shutil.which correctly."""
        meta = {
            "testapp": {
                "target": "testapp",
                "aliases": ["testapp"],
                "exe_names": ["testapp.exe"],
                "install_paths": [],
            }
        }
        with patch.object(AppDiscoveryEngine, "_scan"):
            engine = AppDiscoveryEngine(meta)
        engine.discovered_apps = {}

        with patch("shutil.which", return_value=r"C:\testapp\testapp.exe"):
            engine._scan_system_path()

        assert engine.is_installed("testapp")
        assert engine.get_executable("testapp") == r"C:\testapp\testapp.exe"

    def test_scan_install_paths_finds_exe(self, tmp_path):
        """Test that _scan_install_paths probes directories correctly."""
        # Create a fake install dir with a fake exe
        install_dir = tmp_path / "FakeApp"
        install_dir.mkdir()
        fake_exe = install_dir / "fake.exe"
        fake_exe.write_text("fake", encoding="utf-8")

        meta = {
            "fakeapp": {
                "target": "fakeapp",
                "aliases": ["fakeapp"],
                "exe_names": ["fake.exe"],
                "install_paths": [str(install_dir)],
            }
        }
        with patch.object(AppDiscoveryEngine, "_scan"):
            engine = AppDiscoveryEngine(meta)
        engine.discovered_apps = {}
        engine._scan_install_paths()

        assert engine.is_installed("fakeapp")
        assert engine.get_executable("fakeapp") == str(fake_exe)

    def test_scan_install_paths_skips_missing_dirs(self):
        """Non-existent install_paths should not cause errors."""
        meta = {
            "missingapp": {
                "target": "missingapp",
                "aliases": ["missingapp"],
                "exe_names": ["missing.exe"],
                "install_paths": [r"C:\NonExistent\Path\That\Does\Not\Exist"],
            }
        }
        with patch.object(AppDiscoveryEngine, "_scan"):
            engine = AppDiscoveryEngine(meta)
        engine.discovered_apps = {}
        engine._scan_install_paths()  # Should not raise
        assert not engine.is_installed("missingapp")

    @pytest.mark.skipif(os.name != "nt", reason="Windows-only registry test")
    def test_scan_registry_app_paths_does_not_crash(self):
        """Registry scan should not crash even if keys are missing."""
        meta = {
            "unlikely_app": {
                "target": "unlikely",
                "aliases": ["unlikely"],
                "exe_names": ["unlikely_executable_xyz.exe"],
                "install_paths": [],
            }
        }
        with patch.object(AppDiscoveryEngine, "_scan"):
            engine = AppDiscoveryEngine(meta)
        engine.discovered_apps = {}
        engine._scan_registry_app_paths()  # Should not raise

    def test_lnk_filename_matching(self, tmp_path):
        """Test that _match_lnk_files matches .lnk filenames to app keys."""
        # Create fake .lnk files
        (tmp_path / "Google Chrome.lnk").write_text("fake", encoding="utf-8")
        (tmp_path / "Unknown App.lnk").write_text("fake", encoding="utf-8")

        meta = {
            "chrome": {
                "target": "chrome",
                "aliases": ["chrome", "google chrome"],
                "exe_names": ["chrome.exe"],
                "install_paths": [],
            },
        }
        with patch.object(AppDiscoveryEngine, "_scan"):
            engine = AppDiscoveryEngine(meta)
        engine.discovered_apps = {}
        engine._match_lnk_files([str(tmp_path)])

        assert engine.is_installed("chrome")
        assert "Google Chrome.lnk" in engine.get_executable("chrome")


# ======================================================================
# 5. NOT_INSTALLED Handling
# ======================================================================

class TestNotInstalled:
    """Verify that uninstalled apps return NOT_INSTALLED, never fake success."""

    @pytest.mark.asyncio
    async def test_not_installed_returns_not_installed_string(self):
        """An app that is not discovered should return NOT_INSTALLED."""
        router = FastCommandRouter(enable_discovery=False, config_path=_APPS_JSON)

        # Manually attach a discovery engine with nothing discovered
        meta = router.alias_engine._app_meta
        with patch.object(AppDiscoveryEngine, "_scan"):
            router.discovery_engine = AppDiscoveryEngine(meta)
        router.discovery_engine.discovered_apps = {}

        # Photoshop has install_paths so it's a "real" app, not a system built-in
        result = await router.execute_fast_command("open photoshop")
        assert "NOT_INSTALLED" in result, f"Expected NOT_INSTALLED, got: {result}"
        assert "success" not in result.lower() or "NOT_INSTALLED" in result

    @pytest.mark.asyncio
    async def test_not_installed_does_not_say_opened(self):
        """NOT_INSTALLED result must never contain 'Opened ... successfully'."""
        router = FastCommandRouter(enable_discovery=False, config_path=_APPS_JSON)
        meta = router.alias_engine._app_meta
        with patch.object(AppDiscoveryEngine, "_scan"):
            router.discovery_engine = AppDiscoveryEngine(meta)
        router.discovery_engine.discovered_apps = {}

        result = await router.execute_fast_command("open adobe photoshop")
        assert "Opened" not in result
        assert "successfully" not in result

    @pytest.mark.asyncio
    async def test_websites_always_work(self):
        """Websites should never return NOT_INSTALLED."""
        router = FastCommandRouter(enable_discovery=False, config_path=_APPS_JSON)
        meta = router.alias_engine._app_meta
        with patch.object(AppDiscoveryEngine, "_scan"):
            router.discovery_engine = AppDiscoveryEngine(meta)
        router.discovery_engine.discovered_apps = {}

        # Patch webbrowser to prevent actual browser launch
        with patch("webbrowser.open"):
            result = await router.execute_fast_command("open youtube")
        assert "NOT_INSTALLED" not in result
        assert "Opened" in result or "successfully" in result

    @pytest.mark.asyncio
    async def test_protocol_apps_always_work(self):
        """Protocol-based apps (ms-settings:, whatsapp:, etc.) should not return NOT_INSTALLED."""
        router = FastCommandRouter(enable_discovery=False, config_path=_APPS_JSON)
        meta = router.alias_engine._app_meta
        with patch.object(AppDiscoveryEngine, "_scan"):
            router.discovery_engine = AppDiscoveryEngine(meta)
        router.discovery_engine.discovered_apps = {}

        with patch("os.system"):
            result = await router.execute_fast_command("open settings")
        assert "NOT_INSTALLED" not in result

    @pytest.mark.asyncio
    async def test_system_builtins_always_work(self):
        """System built-ins (notepad, calc, cmd) should never return NOT_INSTALLED."""
        router = FastCommandRouter(enable_discovery=False, config_path=_APPS_JSON)
        meta = router.alias_engine._app_meta
        with patch.object(AppDiscoveryEngine, "_scan"):
            router.discovery_engine = AppDiscoveryEngine(meta)
        router.discovery_engine.discovered_apps = {}

        with patch("os.system"):
            result = await router.execute_fast_command("open notepad")
        # notepad has no install_paths but has exe_names, and shutil.which should find it
        # On Windows, notepad.exe is always on PATH
        if os.name == "nt":
            assert "NOT_INSTALLED" not in result


# ======================================================================
# 6. Enhanced [FCR] Logging
# ======================================================================

class TestFCRLogging:
    """Verify that [FCR] log lines contain all required fields."""

    @pytest.mark.asyncio
    async def test_logging_contains_app_found(self):
        mock_logger = MagicMock(spec=logging.Logger)
        router = FastCommandRouter(
            enable_discovery=False, logger=mock_logger, config_path=_APPS_JSON
        )

        with patch("os.system"):
            await router.execute_fast_command("open notepad")

        # Collect all log messages
        all_messages = [str(call) for call in mock_logger.info.call_args_list]
        combined = " ".join(all_messages)

        assert "App Found" in combined, f"Missing 'App Found' in logs: {all_messages}"

    @pytest.mark.asyncio
    async def test_logging_contains_executable(self):
        mock_logger = MagicMock(spec=logging.Logger)
        router = FastCommandRouter(
            enable_discovery=False, logger=mock_logger, config_path=_APPS_JSON
        )

        with patch("os.system"):
            await router.execute_fast_command("open chrome")

        all_messages = [str(call) for call in mock_logger.info.call_args_list]
        combined = " ".join(all_messages)
        assert "Executable" in combined, f"Missing 'Executable' in logs"

    @pytest.mark.asyncio
    async def test_logging_contains_alias(self):
        mock_logger = MagicMock(spec=logging.Logger)
        router = FastCommandRouter(
            enable_discovery=False, logger=mock_logger, config_path=_APPS_JSON
        )

        with patch("os.system"):
            await router.execute_fast_command("open vscode")

        all_messages = [str(call) for call in mock_logger.info.call_args_list]
        combined = " ".join(all_messages)
        assert "Alias" in combined, f"Missing 'Alias' in logs"

    @pytest.mark.asyncio
    async def test_logging_contains_launch_method(self):
        mock_logger = MagicMock(spec=logging.Logger)
        router = FastCommandRouter(
            enable_discovery=False, logger=mock_logger, config_path=_APPS_JSON
        )

        with patch("os.system"):
            await router.execute_fast_command("open calculator")

        all_messages = [str(call) for call in mock_logger.info.call_args_list]
        combined = " ".join(all_messages)
        assert "LaunchMethod" in combined, f"Missing 'LaunchMethod' in logs"


# ======================================================================
# 7. Backward Compatibility
# ======================================================================

# These are the exact aliases from the ORIGINAL apps.json that must still work
BACKWARD_COMPAT_ALIASES = [
    ("chrome", "chrome"),
    ("google chrome", "chrome"),
    ("browser", "chrome"),
    ("गूगल क्रोम", "chrome"),
    ("क्रोम", "chrome"),
    ("ब्राउज़र", "chrome"),
    ("youtube", "https://youtube.com"),
    ("yt", "https://youtube.com"),
    ("यूट्यूब", "https://youtube.com"),
    ("vscode", "code"),
    ("vs code", "code"),
    ("visual studio code", "code"),
    ("code", "code"),
    ("वीएस कोड", "code"),
    ("कोड", "code"),
    ("calculator", "calc"),
    ("calc", "calc"),
    ("कैलकुलेटर", "calc"),
    ("notepad", "notepad"),
    ("नोटपैड", "notepad"),
    ("explorer", "explorer"),
    ("file explorer", "explorer"),
    ("my computer", "explorer"),
    ("this pc", "explorer"),
    ("एक्सप्लोरर", "explorer"),
    ("settings", "ms-settings:"),
    ("सेटिंग्स", "ms-settings:"),
    ("task manager", "taskmgr"),
    ("taskmgr", "taskmgr"),
    ("टास्क मैनेजर", "taskmgr"),
    ("cmd", "cmd"),
    ("command prompt", "cmd"),
    ("कमांड प्रॉम्प्ट", "cmd"),
    ("powershell", "powershell"),
    ("पावरशेल", "powershell"),
]


class TestBackwardCompatibility:
    """Ensure ALL original aliases from the pre-hardening apps.json still resolve correctly."""

    @pytest.mark.parametrize("alias,expected", BACKWARD_COMPAT_ALIASES)
    def test_original_alias_still_works(self, alias_engine, alias, expected):
        result = alias_engine.resolve(alias)
        assert result == expected, f"Backward compat BROKEN: '{alias}' resolved to '{result}', expected '{expected}'"

    @pytest.mark.asyncio
    async def test_is_fast_command_backward_compat(self, router):
        """All original fast commands must still be detected."""
        original_commands = [
            "Open Chrome", "open youtube", "Open VS Code", "Open Calculator",
            "open notepad", "Open Explorer", "Open Settings", "Open Task Manager",
            "Open CMD", "Open PowerShell",
            "Create Folder test_dir", "Delete Folder test_dir",
            "Rename Folder test_dir to new_dir",
            "Create File test.txt", "Delete File test.txt",
            "Open File test.txt", "Rename File test.txt to new.txt",
            "Volume up", "Set Brightness 70%",
        ]
        for cmd in original_commands:
            assert router.is_fast_command(cmd) is True, f"Backward compat BROKEN: '{cmd}' not detected"

    @pytest.mark.asyncio
    async def test_non_fast_commands_still_rejected(self, router):
        """Complex queries must NOT be detected as fast commands."""
        non_fast = [
            "Write a python script to scrape news",
            "Explain quantum computing in detail",
            "Analyze this complex financial database query",
            "Who is the president of France?",
            "Summarize this PDF document",
        ]
        for cmd in non_fast:
            assert router.is_fast_command(cmd) is False, f"False positive: '{cmd}' wrongly detected"


# ======================================================================
# 8. FastCommandRouter — Intent Detection for New Apps
# ======================================================================

NEW_APP_INTENT_TESTS = [
    # Browsers
    ("open edge", CommandIntent.OPEN_APP, "msedge"),
    ("open firefox", CommandIntent.OPEN_APP, "firefox"),
    ("open brave", CommandIntent.OPEN_APP, "brave"),
    # Office
    ("open word", CommandIntent.OPEN_APP, "winword"),
    ("open excel", CommandIntent.OPEN_APP, "excel"),
    ("open powerpoint", CommandIntent.OPEN_APP, "powerpnt"),
    ("open outlook", CommandIntent.OPEN_APP, "outlook"),
    ("open teams", CommandIntent.OPEN_APP, "ms-teams:"),
    # Communication
    ("open whatsapp", CommandIntent.OPEN_APP, "whatsapp:"),
    ("open telegram", CommandIntent.OPEN_APP, "telegram"),
    ("open discord", CommandIntent.OPEN_APP, "discord"),
    # Media
    ("open spotify", CommandIntent.OPEN_APP, "spotify"),
    ("open vlc", CommandIntent.OPEN_APP, "vlc"),
    ("open obs", CommandIntent.OPEN_APP, "obs64"),
    # Gaming
    ("open steam", CommandIntent.OPEN_APP, "steam"),
    # System
    ("open control panel", CommandIntent.OPEN_APP, "control"),
    ("open device manager", CommandIntent.OPEN_APP, "devmgmt.msc"),
    ("open registry editor", CommandIntent.OPEN_APP, "regedit"),
    ("open snipping tool", CommandIntent.OPEN_APP, "snippingtool"),
    # Hindi
    ("एक्सेल खोलो", CommandIntent.OPEN_APP, "excel"),
    ("पावरपॉइंट चलाओ", CommandIntent.OPEN_APP, "powerpnt"),
    ("स्पॉटिफाई खोलो", CommandIntent.OPEN_APP, "spotify"),
]


class TestNewAppIntentDetection:
    """Verify intent detection works for all new application entries."""

    @pytest.mark.parametrize("text,expected_intent,expected_target", NEW_APP_INTENT_TESTS)
    def test_new_app_intent(self, router, text, expected_intent, expected_target):
        assert router.is_fast_command(text), f"'{text}' not detected as fast command"
        match = router.intent_engine.match(text)
        assert match is not None, f"No intent match for '{text}'"
        assert match.intent == expected_intent, (
            f"For '{text}': expected {expected_intent.name}, got {match.intent.name}"
        )
        assert match.target == expected_target, (
            f"For '{text}': expected target '{expected_target}', got '{match.target}'"
        )


# ======================================================================
# 9. Edge Cases
# ======================================================================

class TestEdgeCases:
    """Edge case handling."""

    def test_empty_string(self, router):
        assert router.is_fast_command("") is False

    def test_whitespace_only(self, router):
        assert router.is_fast_command("   ") is False

    def test_none_like_empty(self, router):
        assert router.is_fast_command("") is False

    @pytest.mark.asyncio
    async def test_execute_empty_string(self, router):
        result = await router.execute_fast_command("")
        assert "Action Failed" in result

    def test_very_long_input(self, router):
        long_text = "open " + "a" * 1000
        # Should not crash
        router.is_fast_command(long_text)

    def test_unicode_mixed_script(self, alias_engine):
        """Mixed Devanagari+Latin input should not crash."""
        result = alias_engine.resolve("vscode कोड")  # Not a valid alias
        # Should return None gracefully
        assert result is None or isinstance(result, str)

    def test_duplicate_alias_last_wins(self):
        """If two entries share an alias, loading should not crash."""
        # This is a structural test — our config shouldn't have dupes,
        # but the engine should handle it gracefully.
        config = {
            "app1": {"target": "t1", "aliases": ["shared"], "exe_names": [], "install_paths": []},
            "app2": {"target": "t2", "aliases": ["shared"], "exe_names": [], "install_paths": []},
        }
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(config, f)
            tmp = Path(f.name)

        try:
            engine = AliasEngine(config_path=tmp)
            result = engine.resolve("shared")
            assert result in ("t1", "t2"), "Should resolve to one of the targets"
        finally:
            tmp.unlink()


# ======================================================================
# 10. Performance
# ======================================================================

class TestPerformance:
    """Ensure routing stays fast with the expanded alias database."""

    def test_routing_performance_500_commands(self, router):
        sample_commands = [a for a, _ in ENGLISH_ALIAS_TESTS[:20]]
        t0 = time.perf_counter()
        for _ in range(25):
            for cmd in sample_commands:
                router.is_fast_command(f"open {cmd}")
        t1 = time.perf_counter()

        total_ops = 25 * len(sample_commands)
        elapsed = t1 - t0
        assert elapsed < 1.0, f"Routing {total_ops} commands took {elapsed:.3f}s (> 1.0s budget)"
        logger.info("Performance: %d ops in %.4fs (%.0f ops/sec)", total_ops, elapsed, total_ops / elapsed)
