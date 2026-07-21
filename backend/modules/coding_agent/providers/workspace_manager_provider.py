from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from backend.modules.coding_agent._exceptions import WorkspaceError
from backend.modules.coding_agent.ports.workspace_manager_port import WorkspaceManagerPort

_LOG = logging.getLogger("naira.coding_agent.workspace")


class TempWorkspaceManagerProvider(WorkspaceManagerPort):
    """Default provider for the Workspace Manager port.

    Manages agent workspaces using temporary directories.
    """

    def __init__(
        self,
        *,
        base_dir: str | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._logger = logger or _LOG
        self._available: bool = True
        self._base_dir = Path(base_dir) if base_dir else Path.cwd() / ".coding_agent_workspaces"
        self._workspaces: dict[str, dict[str, Any]] = {}
        self._states: dict[str, dict[str, Any]] = {}

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def provider_name(self) -> str:
        return "temp_workspace_manager"

    async def create_workspace(
        self,
        session_id: str,
        project_path: str | None = None,
    ) -> dict[str, Any]:
        try:
            self._base_dir.mkdir(parents=True, exist_ok=True)
            if project_path:
                workspace_path = Path(project_path)
            else:
                workspace_path = self._base_dir / f"ws_{session_id}"
                workspace_path.mkdir(parents=True, exist_ok=True)
            info = {
                "path": str(workspace_path.resolve()),
                "session_id": session_id,
                "created_at": time.time(),
            }
            self._workspaces[session_id] = info
            self._logger.debug("Created workspace: %s", info["path"])
            return info
        except Exception as exc:
            raise WorkspaceError(f"Failed to create workspace: {exc}") from exc

    async def get_workspace(
        self,
        session_id: str,
    ) -> dict[str, Any]:
        ws = self._workspaces.get(session_id)
        if ws is None:
            raise WorkspaceError(f"Workspace not found: {session_id}")
        return ws

    async def cleanup_workspace(
        self,
        session_id: str,
    ) -> None:
        ws = self._workspaces.pop(session_id, None)
        self._states.pop(session_id, None)
        if ws:
            import shutil
            path = Path(ws["path"])
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)
                self._logger.debug("Cleaned up workspace: %s", path)

    async def save_state(
        self,
        session_id: str,
        state: dict[str, Any],
    ) -> None:
        self._states[session_id] = state
        self._logger.debug("Saved state for session: %s", session_id)

    async def load_state(
        self,
        session_id: str,
    ) -> dict[str, Any]:
        state = self._states.get(session_id)
        if state is None:
            return {}
        return dict(state)

    async def close(self) -> None:
        self._available = False
        for sid in list(self._workspaces.keys()):
            await self.cleanup_workspace(sid)
        self._logger.info("Workspace manager provider closed")
