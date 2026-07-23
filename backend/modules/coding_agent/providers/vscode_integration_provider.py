"""VSCodeIntegrationProvider — VS Code integration via CLI and direct file operations."""

from __future__ import annotations

import asyncio
import difflib
import logging
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any

from backend.modules.coding_agent.ports.file_manager_port import FileManagerPort
from backend.modules.coding_agent.ports.workspace_manager_port import WorkspaceManagerPort

_LOG = logging.getLogger("naira.coding_agent.vscode")


class VSCodeIntegrationProvider:
    """VS Code integration provider for editor automation."""

    def __init__(
        self,
        *,
        file_manager: FileManagerPort | None = None,
        workspace_manager: WorkspaceManagerPort | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._file_manager = file_manager
        self._workspace_manager = workspace_manager
        self._logger = logger or _LOG

    @property
    def is_available(self) -> bool:
        return shutil.which("code") is not None

    async def open_folder(
        self, folder_path: str, new_window: bool = False
    ) -> dict[str, Any]:
        if not self.is_available:
            return {
                "success": False,
                "error": "VS Code CLI not found on PATH. Ensure 'code' command is installed.",
            }

        def _run() -> tuple[bool, str]:
            args = ["code", "-n", folder_path] if new_window else ["code", folder_path]
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=15,
                shell=(os.name == "nt"),
            )
            return result.returncode == 0, result.stderr

        success, error = await asyncio.to_thread(_run)
        return {
            "success": success,
            "error": error if not success else None,
            "folder": folder_path,
        }

    async def open_file(
        self, file_path: str, line_number: int | None = None
    ) -> dict[str, Any]:
        if not self.is_available:
            return {
                "success": False,
                "error": "VS Code CLI not found on PATH. Ensure 'code' command is installed.",
            }

        def _run() -> tuple[bool, str]:
            target = f"{file_path}:{line_number}" if line_number else file_path
            args = ["code", "-g", target]
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=15,
                shell=(os.name == "nt"),
            )
            return result.returncode == 0, result.stderr

        success, error = await asyncio.to_thread(_run)
        return {
            "success": success,
            "error": error if not success else None,
            "file": file_path,
        }

    async def create_project_structure(
        self, base_path: str, structure: dict[str, Any]
    ) -> dict[str, Any]:
        if not self.is_available:
            return {
                "success": False,
                "error": "VS Code CLI not found on PATH. Ensure 'code' command is installed.",
            }

        base = Path(base_path).resolve()
        created_files: list[str] = []

        async def _create_recursive(curr_dir: Path, curr_struct: dict[str, Any]) -> None:
            curr_dir.mkdir(parents=True, exist_ok=True)
            for key, value in curr_struct.items():
                target_path = curr_dir / key
                if isinstance(value, dict):
                    await _create_recursive(target_path, value)
                elif isinstance(value, str):
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    if self._file_manager:
                        await self._file_manager.create_file(str(target_path), value)
                    else:
                        target_path.write_text(value, encoding="utf-8")
                    created_files.append(str(target_path))
                elif value is None:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    if self._file_manager:
                        await self._file_manager.create_file(str(target_path), "")
                    else:
                        target_path.write_text("", encoding="utf-8")
                    created_files.append(str(target_path))

        try:
            await _create_recursive(base, structure)
            open_res = await self.open_folder(str(base), new_window=True)
            return {
                "success": open_res.get("success", False),
                "error": open_res.get("error"),
                "base_path": str(base),
                "created_files": created_files,
            }
        except Exception as exc:
            return {
                "success": False,
                "error": str(exc),
                "base_path": str(base),
                "created_files": created_files,
            }

    async def edit_file_in_project(
        self, file_path: str, new_content: str, create_backup: bool = True
    ) -> dict[str, Any]:
        path = Path(file_path).resolve()
        backup_path = None
        try:
            if create_backup and path.exists():
                backup_path = str(path) + ".bak"
                if self._file_manager:
                    existing = await self._file_manager.read_file(str(path))
                    await self._file_manager.write_file(backup_path, existing)
                else:
                    shutil.copy2(path, backup_path)

            if self._file_manager:
                await self._file_manager.write_file(str(path), new_content)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(new_content, encoding="utf-8")

            return {
                "success": True,
                "error": None,
                "file_path": str(path),
                "backup_path": backup_path,
            }
        except Exception as exc:
            return {
                "success": False,
                "error": str(exc),
                "file_path": str(path),
                "backup_path": backup_path,
            }

    async def run_in_integrated_terminal(
        self, command: str, cwd: str | None = None
    ) -> dict[str, Any]:
        def _run() -> tuple[bool, str, str]:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            return result.returncode == 0, result.stdout, result.stderr

        try:
            success, stdout, stderr = await asyncio.to_thread(_run)
            return {
                "success": success,
                "stdout": stdout,
                "stderr": stderr,
                "command": command,
            }
        except Exception as exc:
            return {"success": False, "error": str(exc), "command": command}

    async def install_extension(self, extension_id: str) -> dict[str, Any]:
        if not self.is_available:
            return {
                "success": False,
                "error": "VS Code CLI not found on PATH. Ensure 'code' command is installed.",
            }

        def _run() -> tuple[bool, str, str]:
            args = ["code", "--install-extension", extension_id]
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=60,
                shell=(os.name == "nt"),
            )
            return result.returncode == 0, result.stdout, result.stderr

        try:
            success, stdout, stderr = await asyncio.to_thread(_run)
            return {
                "success": success,
                "error": stderr if not success else None,
                "extension_id": extension_id,
                "output": stdout,
            }
        except Exception as exc:
            return {"success": False, "error": str(exc), "extension_id": extension_id}

    async def list_open_files(self, workspace_path: str) -> list[str]:
        def _list() -> list[str]:
            base = Path(workspace_path).resolve()
            if not base.exists() or not base.is_dir():
                return []
            files: list[str] = []
            for p in base.rglob("*"):
                if p.is_file() and not any(part.startswith(".") for part in p.parts):
                    files.append(str(p))
            return files

        return await asyncio.to_thread(_list)
