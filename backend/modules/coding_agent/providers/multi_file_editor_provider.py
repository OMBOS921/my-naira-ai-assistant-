from __future__ import annotations

import difflib
import logging
from typing import Any

from backend.modules.coding_agent._exceptions import FileOperationError
from backend.modules.coding_agent.ports.multi_file_editor_port import MultiFileEditorPort

_LOG = logging.getLogger("naira.coding_agent.editor")


class DefaultMultiFileEditorProvider(MultiFileEditorPort):
    """Default provider for the Multi-File Editor port.

    Provides patch generation, diff creation, and multi-file editing.
    """

    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._logger = logger or _LOG
        self._available: bool = True

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def provider_name(self) -> str:
        return "default_editor"

    async def create_patch(
        self,
        file_path: str,
        old_content: str,
        new_content: str,
    ) -> str:
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
        )
        return "".join(diff)

    async def apply_patch(
        self,
        file_path: str,
        patch: str,
    ) -> str:
        try:
            import subprocess
            import tempfile

            with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False) as f:
                f.write(patch)
                patch_path = f.name

            result = subprocess.run(
                ["git", "apply", patch_path],
                capture_output=True,
                text=True,
            )
            import os
            os.unlink(patch_path)

            if result.returncode != 0:
                raise FileOperationError(f"Patch apply failed: {result.stderr}")

            from pathlib import Path
            return Path(file_path).read_text(encoding="utf-8")
        except FileOperationError:
            raise
        except Exception as exc:
            raise FileOperationError(f"Failed to apply patch: {exc}") from exc

    async def create_hunk(
        self,
        file_path: str,
        line_start: int,
        line_end: int,
        content: str,
    ) -> dict[str, Any]:
        return {
            "file_path": file_path,
            "line_start": line_start,
            "line_end": line_end,
            "content": content,
        }

    async def edit_multiple(
        self,
        edits: list[dict[str, Any]],
    ) -> dict[str, Any]:
        results: dict[str, Any] = {"success": [], "failed": [], "errors": {}}
        for edit in edits:
            file_path = edit.get("file_path", "")
            action = edit.get("action", "")
            try:
                if action == "create":
                    from pathlib import Path
                    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
                    Path(file_path).write_text(edit.get("content", ""), encoding="utf-8")
                    results["success"].append(file_path)
                elif action == "write":
                    from pathlib import Path
                    Path(file_path).write_text(edit.get("content", ""), encoding="utf-8")
                    results["success"].append(file_path)
                elif action == "delete":
                    from pathlib import Path
                    Path(file_path).unlink(missing_ok=True)
                    results["success"].append(file_path)
                else:
                    results["failed"].append(file_path)
                    results["errors"][file_path] = f"Unknown action: {action}"
            except Exception as exc:
                results["failed"].append(file_path)
                results["errors"][file_path] = str(exc)
        return results

    async def close(self) -> None:
        self._available = False
        self._logger.info("Multi-file editor provider closed")
