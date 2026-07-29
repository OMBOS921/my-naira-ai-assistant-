"""Unit tests for LocalPythonExecutor in backend/modules/coding_agent/_python_executor.py."""

from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.modules.coding_agent._exceptions import SafetyViolationError
from backend.modules.coding_agent._python_executor import (
    LocalPythonExecutor,
    PythonExecutionResult,
)
from backend.modules.coding_agent.providers.command_executor_provider import (
    AsyncCommandExecutorProvider,
)
from backend.modules.coding_agent.providers.file_manager_provider import (
    OSFileManagerProvider,
)
from backend.modules.coding_agent.providers.safety_layer_provider import (
    DefaultSafetyLayerProvider,
)


class TestLocalPythonExecutor:
    @pytest.mark.asyncio
    async def test_successful_script_execution(self, tmp_path) -> None:
        executor = LocalPythonExecutor(workspace_dir=str(tmp_path))
        script = 'print("Hello from Naira-OS LocalPythonExecutor!")'

        result = await executor.execute(script)

        assert isinstance(result, PythonExecutionResult)
        assert result.success is True
        assert "Hello from Naira-OS LocalPythonExecutor!" in result.stdout
        assert result.return_code == 0
        assert result.error is None
        assert result.duration_ms > 0

        # Verify to_dict serialization
        res_dict = result.to_dict()
        assert res_dict["success"] is True
        assert "Hello from Naira-OS LocalPythonExecutor!" in res_dict["stdout"]

    @pytest.mark.asyncio
    async def test_script_error_execution(self, tmp_path) -> None:
        executor = LocalPythonExecutor(workspace_dir=str(tmp_path))
        script = 'raise ValueError("Custom test failure")'

        result = await executor.execute(script)

        assert isinstance(result, PythonExecutionResult)
        assert result.success is False
        assert "ValueError: Custom test failure" in result.stderr
        assert result.return_code != 0
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_destructive_script_rejection(self, tmp_path) -> None:
        executor = LocalPythonExecutor(workspace_dir=str(tmp_path))
        destructive_script = 'import os; os.system("rm -rf /")'

        with pytest.raises(SafetyViolationError) as exc_info:
            await executor.execute(destructive_script)

        assert "Destructive system command detected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_safety_layer_command_validation_rejection(self, tmp_path) -> None:
        mock_safety = MagicMock(spec=DefaultSafetyLayerProvider)
        mock_safety.validate_file_operation = AsyncMock(return_value=(True, None))
        mock_safety.validate_command = AsyncMock(
            return_value=(False, "Command execution rejected by policy")
        )

        executor = LocalPythonExecutor(
            safety_layer=mock_safety, workspace_dir=str(tmp_path)
        )
        script = 'print("Safe code")'

        with pytest.raises(SafetyViolationError) as exc_info:
            await executor.execute(script)

        assert "Command execution rejected by policy" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_temp_file_cleanup(self, tmp_path) -> None:
        executor = LocalPythonExecutor(workspace_dir=str(tmp_path))
        script = 'print("Cleanup test")'

        result = await executor.execute(script)

        assert result.temp_file_path is not None
        # File should have been deleted automatically in finally block
        assert not os.path.exists(result.temp_file_path)

    @pytest.mark.asyncio
    async def test_temp_file_cleanup_on_error(self, tmp_path) -> None:
        executor = LocalPythonExecutor(workspace_dir=str(tmp_path))
        script = 'import sys; print("Failing"); sys.exit(1)'

        result = await executor.execute(script)

        assert result.temp_file_path is not None
        assert not os.path.exists(result.temp_file_path)
