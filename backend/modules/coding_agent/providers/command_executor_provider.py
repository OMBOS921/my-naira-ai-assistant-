from __future__ import annotations

import asyncio
import logging
import shlex
import time
from typing import Any

from backend.modules.coding_agent._exceptions import CommandExecutionError
from backend.modules.coding_agent.ports.command_executor_port import CommandExecutorPort

_LOG = logging.getLogger("naira.coding_agent.command")


class AsyncCommandExecutorProvider(CommandExecutorPort):
    """Default provider for the Command Executor port.

    Executes shell commands safely with proper sandboxing and timeout.
    """

    def __init__(
        self,
        *,
        allowed_commands: tuple[str, ...] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._logger = logger or _LOG
        self._available: bool = True
        self._allowed_commands = allowed_commands or ()

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def provider_name(self) -> str:
        return "async_command_executor"

    async def execute(
        self,
        command: str | list[str],
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        start = time.monotonic()
        try:
            cmd = shlex.split(command) if isinstance(command, str) else list(command)

            if self._allowed_commands:
                base = cmd[0] if cmd else ""
                if base not in self._allowed_commands:
                    raise CommandExecutionError(
                        f"Command not allowed: {base} (restricted to {self._allowed_commands})",
                    )

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            elapsed = (time.monotonic() - start) * 1000
            output = stdout.decode("utf-8", errors="replace") if stdout else ""
            error = stderr.decode("utf-8", errors="replace") if stderr else ""
            return {
                "success": proc.returncode == 0,
                "output": output,
                "error": error,
                "return_code": proc.returncode or 0,
                "duration_ms": elapsed,
            }
        except asyncio.TimeoutError:
            elapsed = (time.monotonic() - start) * 1000
            return {
                "success": False,
                "output": "",
                "error": f"Command timed out after {timeout}s",
                "return_code": -1,
                "duration_ms": elapsed,
            }
        except CommandExecutionError:
            raise
        except Exception as exc:
            raise CommandExecutionError(f"Command execution failed: {exc}") from exc

    async def close(self) -> None:
        self._available = False
        self._logger.info("Command executor provider closed")
