from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.modules.coding_agent._exceptions import GitOperationError
from backend.modules.coding_agent.ports.git_executor_port import GitExecutorPort

_LOG = logging.getLogger("naira.coding_agent.git")


class CLIGitExecutorProvider(GitExecutorPort):
    """Default provider for the Git Executor port.

    Executes Git commands via the CLI with proper repository context.
    """

    def __init__(
        self,
        *,
        enabled: bool = True,
        logger: logging.Logger | None = None,
    ) -> None:
        self._logger = logger or _LOG
        self._available: bool = enabled
        self._enabled = enabled

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def provider_name(self) -> str:
        return "cli_git"

    async def execute(
        self,
        args: list[str],
        *,
        cwd: str | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        if not self._enabled:
            return {"success": False, "output": "", "error": "Git disabled", "return_code": -1}
        try:
            cmd = ["git"] + args
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            output = stdout.decode("utf-8", errors="replace") if stdout else ""
            error = stderr.decode("utf-8", errors="replace") if stderr else ""
            return {
                "success": proc.returncode == 0,
                "output": output,
                "error": error,
                "return_code": proc.returncode or 0,
            }
        except asyncio.TimeoutError as exc:
            raise GitOperationError(f"Git command timed out: {' '.join(args)}") from exc
        except Exception as exc:
            raise GitOperationError(f"Git command failed: {exc}") from exc
    async def commit(
        self,
        message: str,
        *,
        cwd: str | None = None,
    ) -> dict[str, Any]:
        return await self.execute(["commit", "-m", message], cwd=cwd)

    async def push(
        self,
        remote: str = "origin",
        branch: str = "main",
        *,
        cwd: str | None = None,
    ) -> dict[str, Any]:
        return await self.execute(["push", remote, branch], cwd=cwd)

    async def pull(
        self,
        remote: str = "origin",
        branch: str = "main",
        *,
        cwd: str | None = None,
    ) -> dict[str, Any]:
        return await self.execute(["pull", remote, branch], cwd=cwd)

    async def diff(
        self,
        *,
        cwd: str | None = None,
    ) -> str:
        result = await self.execute(["diff"], cwd=cwd)
        return result.get("output", "")

    async def status(
        self,
        *,
        cwd: str | None = None,
    ) -> dict[str, Any]:
        result = await self.execute(["status", "--porcelain"], cwd=cwd)
        output = result.get("output", "")
        lines = [ln for ln in output.split("\n") if ln.strip()]
        modified = []
        staged = []
        untracked = []
        for line in lines:
            if len(line) < 3:
                continue
            status_code = line[:2]
            filepath = line[3:]
            if status_code == "??":
                untracked.append(filepath)
            elif status_code[0] != " ":
                staged.append(filepath)
            else:
                modified.append(filepath)
        return {
            "modified": modified,
            "staged": staged,
            "untracked": untracked,
        }

    async def close(self) -> None:
        self._available = False
        self._logger.info("Git executor provider closed")
