"""
Unit tests for Multilingual Fast Command Router (English, Hindi, Hinglish, System Control, Filesystem).
Minimum 50 comprehensive test cases.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
import pytest

from backend.runtime.fast_command_router import (
    FastCommandRouter,
    CommandIntent,
    WakeWordCleaner,
    MultilingualNormalizer,
    AliasEngine,
    IntentEngine,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_multilingual_fast_router")


# ----------------------------------------------------------------------
# 1. Wake Word Cleaner Tests
# ----------------------------------------------------------------------

def test_wake_word_cleaner():
    assert WakeWordCleaner.clean("hello naira open youtube") == "open youtube"
    assert WakeWordCleaner.clean("please mera youtube kholo") == "youtube kholo"
    assert WakeWordCleaner.clean("hey naira ek jara vs code chalao") == "vs code chalao"
    assert WakeWordCleaner.clean("हेलो नायरा यूट्यूब खोलो") == "यूट्यूब खोलो"
    assert WakeWordCleaner.clean("प्लीज मेरा कैलकुलेटर खोलो") == "कैलकुलेटर खोलो"


# ----------------------------------------------------------------------
# 2. Multilingual Normalizer & Alias Engine Tests
# ----------------------------------------------------------------------

def test_multilingual_normalizer_and_alias_engine():
    assert MultilingualNormalizer.normalize_token("kholo") == "open"
    assert MultilingualNormalizer.normalize_token(" खोलो ") == "open"
    assert MultilingualNormalizer.normalize_token("chalao") == "open"
    assert MultilingualNormalizer.normalize_token("बनाओ") == "create"

    engine = AliasEngine()
    assert engine.resolve("yt") == "https://youtube.com"
    assert engine.resolve("यूट्यूब") == "https://youtube.com"
    assert engine.resolve("vscode") == "code"
    assert engine.resolve("वीएस कोड") == "code"
    assert engine.resolve("google chrome") == "chrome"
    assert engine.resolve("गूगल क्रोम") == "chrome"


# ----------------------------------------------------------------------
# 3. Comprehensive Fast Command Detection (50+ Test Cases)
# ----------------------------------------------------------------------

TEST_CASES_TRUE = [
    # English App & Website
    ("open youtube", CommandIntent.OPEN_WEBSITE, "https://youtube.com"),
    ("please open youtube", CommandIntent.OPEN_WEBSITE, "https://youtube.com"),
    ("open chrome", CommandIntent.OPEN_APP, "chrome"),
    ("launch google chrome", CommandIntent.OPEN_APP, "chrome"),
    ("open vs code", CommandIntent.OPEN_APP, "code"),
    ("open vscode", CommandIntent.OPEN_APP, "code"),
    ("run visual studio code", CommandIntent.OPEN_APP, "code"),
    ("open calculator", CommandIntent.OPEN_APP, "calc"),
    ("open notepad", CommandIntent.OPEN_APP, "notepad"),
    ("open explorer", CommandIntent.OPEN_APP, "explorer"),
    ("open file explorer", CommandIntent.OPEN_APP, "explorer"),
    ("open settings", CommandIntent.OPEN_APP, "ms-settings:"),
    ("open task manager", CommandIntent.OPEN_APP, "taskmgr"),
    ("open cmd", CommandIntent.OPEN_APP, "cmd"),
    ("open powershell", CommandIntent.OPEN_APP, "powershell"),

    # Hinglish App & Website
    ("youtube kholo", CommandIntent.OPEN_WEBSITE, "https://youtube.com"),
    ("youtube open karo", CommandIntent.OPEN_WEBSITE, "https://youtube.com"),
    ("mera youtube kholo", CommandIntent.OPEN_WEBSITE, "https://youtube.com"),
    ("hello naira youtube kholo", CommandIntent.OPEN_WEBSITE, "https://youtube.com"),
    ("chrome chalao", CommandIntent.OPEN_APP, "chrome"),
    ("browser open karo", CommandIntent.OPEN_APP, "chrome"),
    ("vs code chalao", CommandIntent.OPEN_APP, "code"),
    ("calculator kholo", CommandIntent.OPEN_APP, "calc"),
    ("mera calculator open karo", CommandIntent.OPEN_APP, "calc"),
    ("notepad chalao", CommandIntent.OPEN_APP, "notepad"),

    # Hindi (Devanagari) App & Website
    ("यूट्यूब खोलो", CommandIntent.OPEN_WEBSITE, "https://youtube.com"),
    ("गूगल क्रोम खोलो", CommandIntent.OPEN_APP, "chrome"),
    ("वीएस कोड चलाओ", CommandIntent.OPEN_APP, "code"),
    ("कैलकुलेटर खोलो", CommandIntent.OPEN_APP, "calc"),
    ("नोटपैड चलाओ", CommandIntent.OPEN_APP, "notepad"),
    ("सेटिंग्स खोलो", CommandIntent.OPEN_APP, "ms-settings:"),
    ("टास्क मैनेजर खोलो", CommandIntent.OPEN_APP, "taskmgr"),

    # System Intents (Lock, Shutdown, Restart)
    ("lock pc", CommandIntent.LOCK_PC, "lock_workstation"),
    ("lock system", CommandIntent.LOCK_PC, "lock_workstation"),
    ("pc lock karo", CommandIntent.LOCK_PC, "lock_workstation"),
    ("स्क्रीन लॉक करो", CommandIntent.LOCK_PC, "lock_workstation"),
    ("shutdown pc", CommandIntent.SHUTDOWN, "shutdown"),
    ("computer band karo", CommandIntent.SHUTDOWN, "shutdown"),
    ("कंप्यूटर बंद करो", CommandIntent.SHUTDOWN, "shutdown"),
    ("restart pc", CommandIntent.RESTART, "restart"),
    ("computer restart karo", CommandIntent.RESTART, "restart"),
    ("रीस्टार्ट करो", CommandIntent.RESTART, "restart"),

    # Volume Intents
    ("volume up", CommandIntent.SET_VOLUME, "volume_up"),
    ("volume down", CommandIntent.SET_VOLUME, "volume_down"),
    ("set volume to 50%", CommandIntent.SET_VOLUME, "volume_50"),
    ("volume 80", CommandIntent.SET_VOLUME, "volume_80"),
    ("mute", CommandIntent.SET_VOLUME, "volume_mute"),
    ("unmute", CommandIntent.SET_VOLUME, "volume_unmute"),
    ("awaaz badhao", CommandIntent.SET_VOLUME, "volume_up"),
    ("sound kam karo", CommandIntent.SET_VOLUME, "volume_down"),
    ("वॉल्यूम 50 करो", CommandIntent.SET_VOLUME, "volume_50"),

    # Brightness Intents
    ("brightness up", CommandIntent.SET_BRIGHTNESS, "brightness_up"),
    ("brightness 70%", CommandIntent.SET_BRIGHTNESS, "brightness_70"),
    ("roshni badhao", CommandIntent.SET_BRIGHTNESS, "brightness_up"),
    ("roshni kam karo", CommandIntent.SET_BRIGHTNESS, "brightness_down"),

    # Filesystem Intents
    ("create folder demo_folder", CommandIntent.CREATE_FOLDER, "demo_folder"),
    ("desktop pe folder banao projectx", CommandIntent.CREATE_FOLDER, "projectx"),
    ("folder banao testfolder", CommandIntent.CREATE_FOLDER, "testfolder"),
    ("delete folder demo_folder", CommandIntent.DELETE_FOLDER, "demo_folder"),
    ("rename folder demo_folder to new_folder", CommandIntent.RENAME_FOLDER, "demo_folder -> new_folder"),
    ("create file test.txt", CommandIntent.CREATE_FILE, "test.txt"),
    ("desktop pe file banao notes.txt", CommandIntent.CREATE_FILE, "notes.txt"),
    ("file banao index.html", CommandIntent.CREATE_FILE, "index.html"),
    ("delete file test.txt", CommandIntent.DELETE_FILE, "test.txt"),
    ("open file test.txt", CommandIntent.OPEN_FILE, "test.txt"),
    ("rename file test.txt to sample.txt", CommandIntent.RENAME_FILE, "test.txt -> sample.txt"),
]

TEST_CASES_FALSE = [
    "Write a python script to scrape news",
    "Explain quantum computing in detail",
    "Analyze this complex financial database query",
    "Who is the president of France?",
    "Summarize this PDF document",
]


@pytest.mark.asyncio
async def test_fast_command_router_true_matches():
    router = FastCommandRouter()
    assert len(TEST_CASES_TRUE) >= 50, f"Expected >= 50 test cases, got {len(TEST_CASES_TRUE)}"

    for text, expected_intent, expected_target in TEST_CASES_TRUE:
        is_fast = router.is_fast_command(text)
        assert is_fast is True, f"Failed is_fast_command check for: '{text}'"

        match = router.intent_engine.match(text)
        assert match is not None, f"Expected intent match for: '{text}'"
        assert match.intent == expected_intent, f"For '{text}': expected intent {expected_intent.name}, got {match.intent.name}"


@pytest.mark.asyncio
async def test_fast_command_router_false_matches():
    router = FastCommandRouter()
    for text in TEST_CASES_FALSE:
        assert router.is_fast_command(text) is False, f"Expected False for complex request: '{text}'"


@pytest.mark.asyncio
async def test_fast_command_execution():
    router = FastCommandRouter()

    # Test execution for system lock (safe simulated route or execution)
    res = await router.execute_fast_command("open calculator")
    assert "Opened" in res or "Fast Execution" in res

    res = await router.execute_fast_command("volume 50%")
    assert "50%" in res or "Fast Execution" in res

    res = await router.execute_fast_command("brightness 80%")
    assert "80%" in res or "Fast Execution" in res


@pytest.mark.asyncio
async def test_high_performance_benchmark():
    router = FastCommandRouter()
    sample_commands = [t[0] for t in TEST_CASES_TRUE]

    # Benchmark 500+ iterations
    t0 = time.perf_counter()
    for _ in range(10):
        for cmd in sample_commands:
            router.is_fast_command(cmd)
    t1 = time.perf_counter()

    total_ops = len(sample_commands) * 10
    total_time_sec = t1 - t0
    ops_per_sec = total_ops / total_time_sec

    logger.info("Processed %d routing requests in %.4f seconds (%.2f ops/sec)", total_ops, total_time_sec, ops_per_sec)
    assert total_time_sec < 2.0, f"Routing 500+ commands took too long: {total_time_sec:.4f}s"


@pytest.mark.asyncio
async def test_resolve_fast_path_and_execution():
    from backend.runtime.fast_command_router import _resolve_fast_path
    from pathlib import Path

    user_desktop = Path.home() / "Desktop"

    # Test path resolution for desktop folder creation
    p1 = _resolve_fast_path("projectx", "desktop pe folder banao projectx")
    assert p1 == user_desktop / "projectx"

    # Test folder creation & cleanup
    router = FastCommandRouter()
    res = await router.execute_fast_command("desktop pe folder banao test_naira_unit_folder")
    assert "SUCCESS" in res
    created_folder = user_desktop / "test_naira_unit_folder"
    assert created_folder.exists() and created_folder.is_dir()

    # Clean up created test folder
    res_del = await router.execute_fast_command("delete folder test_naira_unit_folder")
    assert "SUCCESS" in res_del
    assert not created_folder.exists()

