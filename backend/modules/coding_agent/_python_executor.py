"""LocalPythonExecutor — safely executes Python code scripts locally.

Integrates:
- FileManagerPort (OSFileManagerProvider) for temporary workspace file operations
- SafetyLayerPort (DefaultSafetyLayerProvider) for security validation
- CommandExecutorPort (AsyncCommandExecutorProvider) for command execution
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass
from typing import Any

from backend.modules.coding_agent._exceptions import (
    CommandExecutionError,
    FileOperationError,
    SafetyViolationError,
)
from backend.modules.coding_agent.ports.command_executor_port import CommandExecutorPort
from backend.modules.coding_agent.ports.file_manager_port import FileManagerPort
from backend.modules.coding_agent.ports.safety_layer_port import SafetyLayerPort
from backend.modules.coding_agent.providers.command_executor_provider import (
    AsyncCommandExecutorProvider,
)
from backend.modules.coding_agent.providers.file_manager_provider import (
    OSFileManagerProvider,
)
from backend.modules.coding_agent.providers.safety_layer_provider import (
    DefaultSafetyLayerProvider,
)

_LOG = logging.getLogger("naira.coding_agent.python_executor")

# Regex patterns for destructive or dangerous operations in raw Python scripts
_DESTRUCTIVE_SCRIPT_PATTERNS: list[tuple[str, str]] = [
    (
        r"(?:os\.system|subprocess\.(?:call|Popen|run))\s*\(\s*['\"](?:.*?\b(?:rm|del|rd|rmdir|format|mkfs|dd|shutdown|reboot|halt|poweroff|killall|pkill|taskkill)\b.*?)['\"]",
        "Destructive system command detected",
    ),
    (
        r"(?:os\.system|subprocess\.(?:call|Popen|run))\s*\(\s*f?['\"].*?-(?:rf|s|q)\b",
        "Force/recursive shell flags detected",
    ),
    (
        r"shutil\.rmtree\s*\(\s*['\"](?:\/|C:\\\\?|C:\/|\.\.)['\"]",
        "Destructive folder deletion targeting root or parent directory",
    ),
    (
        r"(?:rmdir|format|mkfs|dd)\s+-rf\b",
        "Destructive shell command flags detected",
    ),
]


@dataclass
class PythonExecutionResult:
    """Dataclass holding execution results of a local Python script execution."""

    success: bool
    stdout: str
    stderr: str
    return_code: int
    duration_ms: float = 0.0
    error: str | None = None
    temp_file_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary representation."""
        return {
            "success": self.success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "return_code": self.return_code,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "temp_file_path": self.temp_file_path,
        }


class LocalPythonExecutor:
    """Execution engine ('Hands') for running Python scripts locally.

    Integrates FileManagerPort, SafetyLayerPort, and CommandExecutorPort to safely
    write, inspect, execute, and clean up temporary Python scripts.
    """

    def __init__(
        self,
        *,
        file_manager: FileManagerPort | None = None,
        safety_layer: SafetyLayerPort | None = None,
        command_executor: CommandExecutorPort | None = None,
        workspace_dir: str = ".coding_agent_workspaces",
        python_executable: str | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._logger = logger or _LOG
        self._file_manager = file_manager or OSFileManagerProvider()
        self._safety_layer = safety_layer or DefaultSafetyLayerProvider()
        self._command_executor = command_executor or AsyncCommandExecutorProvider()
        self._workspace_dir = workspace_dir
        self._python_executable = python_executable or sys.executable

    @property
    def workspace_dir(self) -> str:
        return self._workspace_dir

    async def execute(
        self,
        script_code: str,
        *,
        timeout: float = 30.0,
        python_executable: str | None = None,
    ) -> PythonExecutionResult:
        """Execute Python script code string safely.

        Parameters
        ----------
        script_code : str
            Raw Python script string to execute.
        timeout : float
            Timeout in seconds for script execution (default 30.0s).
        python_executable : str | None
            Optional override for python executable path/command.

        Returns
        -------
        PythonExecutionResult
        """
        start_time = time.monotonic()
        py_exe = python_executable or self._python_executable

        # 1. Pre-scan script code for destructive patterns
        safety_error = self._scan_script_safety(script_code)
        if safety_error:
            self._logger.warning("Safety check failed: %s", safety_error)
            raise SafetyViolationError(
                f"Script execution blocked: {safety_error}",
                context={"script_snippet": script_code[:200]},
            )

        # 2. Prepare workspace and temporary file path
        filename = f"_script_{uuid.uuid4().hex[:12]}.py"
        temp_file_path = os.path.join(self._workspace_dir, filename)

        # Validate file write operation with SafetyLayer
        safe_file_op, file_reason = await self._safety_layer.validate_file_operation(
            "write", temp_file_path
        )
        if not safe_file_op:
            raise SafetyViolationError(
                f"Safety layer blocked file operation: {file_reason}",
                context={"path": temp_file_path},
            )

        # Validate command execution with SafetyLayer
        safe_cmd, cmd_reason = await self._safety_layer.validate_command(
            py_exe, [temp_file_path]
        )
        if not safe_cmd:
            raise SafetyViolationError(
                f"Safety layer blocked command execution: {cmd_reason}",
                context={"command": py_exe, "file": temp_file_path},
            )

        # 3. Write script to temporary file via FileManager
        try:
            await self._file_manager.create_file(temp_file_path, script_code)
        except Exception as exc:
            self._logger.error("Failed to write temporary script file: %s", exc)
            raise FileOperationError(
                f"Failed to create temporary script file: {exc}",
                context={"path": temp_file_path},
            ) from exc

        # 4. Execute command safely with cleanup in finally block
        try:
            cmd = [py_exe, temp_file_path]
            result = await self._command_executor.execute(cmd, timeout=timeout)
            elapsed_ms = (time.monotonic() - start_time) * 1000

            stdout = result.get("output", "")
            stderr = result.get("error", "")
            return_code = result.get("return_code", -1)
            success = result.get("success", False) and return_code == 0

            return PythonExecutionResult(
                success=success,
                stdout=stdout,
                stderr=stderr,
                return_code=return_code,
                duration_ms=elapsed_ms,
                error=stderr if not success else None,
                temp_file_path=temp_file_path,
            )
        except CommandExecutionError:
            raise
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            self._logger.error("Error running script %s: %s", temp_file_path, exc)
            return PythonExecutionResult(
                success=False,
                stdout="",
                stderr=str(exc),
                return_code=-1,
                duration_ms=elapsed_ms,
                error=f"Execution error: {exc}",
                temp_file_path=temp_file_path,
            )
        finally:
            # 5. Clean up temporary file via FileManager
            await self._cleanup_temp_file(temp_file_path)

    def _scan_script_safety(self, script_code: str) -> str | None:
        """Scan raw script text for known dangerous patterns."""
        for pattern, reason in _DESTRUCTIVE_SCRIPT_PATTERNS:
            if re.search(pattern, script_code, re.IGNORECASE):
                return reason
        return None

    async def _cleanup_temp_file(self, file_path: str) -> None:
        """Safely delete temporary script file."""
        try:
            if await self._file_manager.file_exists(file_path):
                await self._file_manager.delete_file(file_path)
                self._logger.debug("Cleaned up temporary script file: %s", file_path)
        except Exception as exc:
            self._logger.warning(
                "Failed to delete temporary script file %s: %s", file_path, exc
            )
