"""
Test & Benchmark Suite for Fast Command Engine (Tasks 4, 5, 6).
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
import pytest

from backend.runtime.fast_command_router import FastCommandRouter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_fast_command_engine")


@pytest.mark.asyncio
async def test_fast_command_detection():
    router = FastCommandRouter()

    # Supported commands
    assert router.is_fast_command("Open Chrome") is True
    assert router.is_fast_command("open youtube") is True
    assert router.is_fast_command("Open VS Code") is True
    assert router.is_fast_command("Open Calculator") is True
    assert router.is_fast_command("open notepad") is True
    assert router.is_fast_command("Open Explorer") is True
    assert router.is_fast_command("Open Settings") is True
    assert router.is_fast_command("Open Task Manager") is True
    assert router.is_fast_command("Open CMD") is True
    assert router.is_fast_command("Open PowerShell") is True
    assert router.is_fast_command("Create Folder test_dir") is True
    assert router.is_fast_command("Delete Folder test_dir") is True
    assert router.is_fast_command("Rename Folder test_dir to new_dir") is True
    assert router.is_fast_command("Create File test.txt") is True
    assert router.is_fast_command("Delete File test.txt") is True
    assert router.is_fast_command("Open File test.txt") is True
    assert router.is_fast_command("Rename File test.txt to new.txt") is True
    assert router.is_fast_command("Volume up") is True
    assert router.is_fast_command("Set Brightness 70%") is True

    # Non-fast commands (must return False to route to Gemini)
    assert router.is_fast_command("Write a python script to scrape news") is False
    assert router.is_fast_command("Explain quantum computing in detail") is False
    assert router.is_fast_command("Analyze this complex financial database query") is False


@pytest.mark.asyncio
async def test_real_command_execution():
    router = FastCommandRouter()
    commands = [
        "Open Calculator",
        "Open Notepad",
        "Open CMD",
        "Create Folder test_folder_fast",
        "Create File test_folder_fast/demo.txt",
        "Rename File test_folder_fast/demo.txt to test_folder_fast/renamed.txt",
        "Delete File test_folder_fast/renamed.txt",
        "Delete Folder test_folder_fast",
        "Volume 50%",
        "Brightness 80%",
    ]

    results = {}
    for cmd in commands:
        t0 = time.time()
        res = await router.execute_fast_command(cmd)
        elapsed = time.time() - t0
        passed = "Action Failed" not in res
        results[cmd] = {"passed": passed, "elapsed": elapsed, "output": res}
        logger.info("Executed '%s' -> Passed: %s (%.3fs)", cmd, passed, elapsed)

    return results


async def run_stress_test(iterations: int = 20):
    router = FastCommandRouter()
    commands = [
        "Open Calculator",
        "Create Folder stress_test_dir",
        "Create File stress_test_dir/file.txt",
        "Rename File stress_test_dir/file.txt to stress_test_dir/renamed.txt",
        "Delete File stress_test_dir/renamed.txt",
        "Delete Folder stress_test_dir",
    ]

    stats = {cmd: {"times": [], "failures": 0} for cmd in commands}

    for iter_idx in range(iterations):
        for cmd in commands:
            t0 = time.time()
            res = await router.execute_fast_command(cmd)
            t1 = time.time()
            dur = t1 - t0
            stats[cmd]["times"].append(dur)
            if "Action Failed" in res:
                stats[cmd]["failures"] += 1
            await asyncio.sleep(0.01)

    summary = {}
    for cmd in commands:
        times = stats[cmd]["times"]
        failures = stats[cmd]["failures"]
        avg_time = sum(times) / len(times)
        max_time = max(times)
        success_rate = ((iterations - failures) / iterations) * 100
        summary[cmd] = {
            "iterations": iterations,
            "success_rate": success_rate,
            "avg_time_sec": avg_time,
            "max_time_sec": max_time,
            "failure_count": failures,
        }
    return summary


if __name__ == "__main__":
    asyncio.run(test_fast_command_detection())
    logger.info("Fast command detection test passed.")
    res = asyncio.run(test_real_command_execution())
    logger.info("Real command execution finished: %s", res)
    stress = asyncio.run(run_stress_test(20))
    logger.info("Stress test finished: %s", stress)
