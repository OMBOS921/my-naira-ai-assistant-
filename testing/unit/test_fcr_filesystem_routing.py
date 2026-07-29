"""Unit tests for FastCommandRouter (FCR) file/folder creation intent detection, execution & verification."""

import os
import tempfile
import pytest
from pathlib import Path

from backend.runtime.fast_command_router import FastCommandRouter, CommandIntent


@pytest.fixture
def fcr():
    return FastCommandRouter()


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_fcr_intent_matching_folder_phrases(fcr):
    queries = [
        "desktop pe folder banao",
        "desktop pe my_project folder banao",
        "create a folder called TestFolder",
        "make a folder named MyData",
        "is naam se folder banao",
        "folder banao",
    ]
    for q in queries:
        match = fcr.intent_engine.match(q)
        assert match is not None, f"Query failed to match intent: {q}"
        assert match.intent == CommandIntent.CREATE_FOLDER, f"Query '{q}' matched wrong intent: {match.intent}"


def test_fcr_intent_matching_file_phrases(fcr):
    queries = [
        "desktop pe file banao",
        "is naam se file banao",
        "make a file named notes.txt",
        "create a file called demo.py",
        "file banao",
    ]
    for q in queries:
        match = fcr.intent_engine.match(q)
        assert match is not None, f"Query failed to match intent: {q}"
        assert match.intent == CommandIntent.CREATE_FILE, f"Query '{q}' matched wrong intent: {match.intent}"


@pytest.mark.asyncio
async def test_fcr_execute_folder_creation_success(fcr, temp_dir, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: temp_dir)
    desktop_dir = temp_dir / "Desktop"
    desktop_dir.mkdir(parents=True, exist_ok=True)

    result = await fcr.execute_fast_command("desktop pe TestFolder folder banao")
    created_path = desktop_dir / "testfolder"

    assert "SUCCESS" in result
    assert os.path.exists(created_path)
    assert created_path.is_dir()


@pytest.mark.asyncio
async def test_fcr_execute_folder_creation_already_exists(fcr, temp_dir, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: temp_dir)
    desktop_dir = temp_dir / "Desktop"
    desktop_dir.mkdir(parents=True, exist_ok=True)
    (desktop_dir / "ExistingFolder").mkdir(parents=True, exist_ok=True)

    result = await fcr.execute_fast_command("desktop pe ExistingFolder folder banao")

    assert "FAILED" in result
    assert "already exist" in result.lower() or "exist" in result.lower()


@pytest.mark.asyncio
async def test_fcr_execute_file_creation_success(fcr, temp_dir, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: temp_dir)
    desktop_dir = temp_dir / "Desktop"
    desktop_dir.mkdir(parents=True, exist_ok=True)

    result = await fcr.execute_fast_command("make a file named notes.txt on desktop")
    created_path = desktop_dir / "notes.txt"

    assert "SUCCESS" in result
    assert os.path.exists(created_path)
    assert created_path.is_file()


@pytest.mark.asyncio
async def test_fcr_execute_file_system_joins_path_and_folder_name(fcr, temp_dir):
    target_dir = temp_dir / "Desktop"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path_str = str(target_dir)

    # Test path + folder_name
    params_folder = {"path": target_path_str, "folder_name": "Naira-Production-Apps"}
    result1 = await fcr._execute_file_system("create_folder", target_path_str, params_folder, "Create a folder named Naira-Production-Apps on Desktop")

    expected_path1 = target_dir / "Naira-Production-Apps"
    assert "SUCCESS" in result1
    assert os.path.exists(expected_path1)
    assert expected_path1.is_dir()

    # Test path + target_name
    params_target = {"path": target_path_str, "target_name": "Naira-Staging-Apps"}
    result2 = await fcr._execute_file_system("create_folder", target_path_str, params_target, "Create a folder named Naira-Staging-Apps on Desktop")

    expected_path2 = target_dir / "Naira-Staging-Apps"
    assert "SUCCESS" in result2
    assert os.path.exists(expected_path2)
    assert expected_path2.is_dir()


@pytest.mark.asyncio
async def test_fcr_execute_multi_task_operations_array(fcr, temp_dir, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: temp_dir)
    desktop_dir = temp_dir / "Desktop"
    desktop_dir.mkdir(parents=True, exist_ok=True)

    parent_path = desktop_dir / "Naira-Apps"

    operations = [
        {"action": "create_folder", "target": "Naira-Apps", "parameters": {"base_path": "desktop", "target_name": "Naira-Apps"}},
        {"action": "create_folder", "target": "sub1", "parameters": {"base_path": str(parent_path), "target_name": "sub1"}},
        {"action": "create_folder", "target": "sub2", "parameters": {"base_path": str(parent_path), "target_name": "sub2"}},
        {"action": "create_folder", "target": "sub3", "parameters": {"base_path": str(parent_path), "target_name": "sub3"}},
        {"action": "create_folder", "target": "sub4", "parameters": {"base_path": str(parent_path), "target_name": "sub4"}},
        {"action": "create_folder", "target": "sub5", "parameters": {"base_path": str(parent_path), "target_name": "sub5"}},
    ]

    result = await fcr._execute_file_system(operations, "Create Naira-Apps and 5 subfolders on desktop")

    assert os.path.exists(parent_path)
    assert parent_path.is_dir()

    for i in range(1, 6):
        sub_path = parent_path / f"sub{i}"
        assert os.path.exists(sub_path), f"Subfolder sub{i} was not created"
        assert sub_path.is_dir()


def test_resolve_smart_path_keywords(temp_dir, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: temp_dir)
    from backend.runtime.fast_command_router import _resolve_smart_path

    # Desktop keyword
    p_desktop = _resolve_smart_path(params={"base_path": "desktop", "target_name": "Project-A"})
    assert p_desktop == temp_dir / "Desktop" / "Project-A"

    # Documents keyword
    p_docs = _resolve_smart_path(params={"base_path": "documents", "target_name": "Report.pdf"})
    assert p_docs == temp_dir / "Documents" / "Report.pdf"

    # Downloads keyword
    p_dl = _resolve_smart_path(params={"base_path": "downloads", "target_name": "archive.zip"})
    assert p_dl == temp_dir / "Downloads" / "archive.zip"


