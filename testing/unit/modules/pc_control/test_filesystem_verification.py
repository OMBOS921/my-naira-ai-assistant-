"""Unit tests for verified filesystem file/folder creation and FileOpResult handling."""

import os
import tempfile
import pytest
from pathlib import Path

from backend.modules.pc_control._types import FileOpResult
from backend.modules.pc_control._production_adapter import ProductionPCControlAdapter, _validate_path_chars
from backend.modules.settings._config import PCControlConfig


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def adapter():
    config = PCControlConfig(sandbox_enabled=False)
    return ProductionPCControlAdapter(config=config)


@pytest.mark.asyncio
async def test_create_directory_success(adapter, temp_dir):
    target_path = temp_dir / "test_folder_success"
    result = await adapter.filesystem_create_directory(str(target_path))

    assert isinstance(result, FileOpResult)
    assert result.success is True
    assert result.error is None
    assert os.path.exists(target_path)
    assert target_path.is_dir()


@pytest.mark.asyncio
async def test_create_file_success(adapter, temp_dir):
    target_path = temp_dir / "test_file_success.txt"
    content = "Hello Naira OS"
    result = await adapter.filesystem_write_file(str(target_path), content, encoding="utf-8")

    assert isinstance(result, FileOpResult)
    assert result.success is True
    assert result.error is None
    assert os.path.exists(target_path)
    assert target_path.is_file()
    assert target_path.read_text(encoding="utf-8") == content


@pytest.mark.asyncio
async def test_create_directory_already_exists(adapter, temp_dir):
    target_path = temp_dir / "existing_folder"
    target_path.mkdir(parents=True, exist_ok=True)

    result = await adapter.filesystem_create_directory(str(target_path))

    assert isinstance(result, FileOpResult)
    assert result.success is False
    assert result.error is not None
    assert "already exists" in result.error.lower()


@pytest.mark.asyncio
async def test_create_file_already_exists(adapter, temp_dir):
    target_path = temp_dir / "existing_file.txt"
    target_path.write_text("existing content", encoding="utf-8")

    result = await adapter.filesystem_write_file(str(target_path), "new content")

    assert isinstance(result, FileOpResult)
    assert result.success is False
    assert result.error is not None
    assert "already exists" in result.error.lower()


@pytest.mark.asyncio
async def test_create_directory_invalid_characters(adapter, temp_dir):
    invalid_path = str(temp_dir / "test<invalid>?folder")
    result = await adapter.filesystem_create_directory(invalid_path)

    assert isinstance(result, FileOpResult)
    assert result.success is False
    assert result.error is not None
    assert "invalid" in result.error.lower()


def test_validate_path_chars():
    valid_path = Path("C:/Users/test/Desktop/valid_folder")
    assert _validate_path_chars(valid_path) is None

    invalid_path = Path("C:/Users/test/Desktop/invalid?folder")
    assert _validate_path_chars(invalid_path) is not None
