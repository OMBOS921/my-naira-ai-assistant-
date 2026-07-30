"""PC Control process management operations — placeholder component.

Provides process listing and termination operations delegated to
the port adapter.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.modules.pc_control._types import ProcessInfo
    from backend.modules.pc_control.ports.pc_control_port import PCControlPort

_LOG = logging.getLogger("naira.pc_control.process")


CRITICAL_SYSTEM_PROCESSES = (
    "csrss", "lsass", "smss", "services", "wininit", "system", "svchost", "system idle process"
)
CRITICAL_SYSTEM_PIDS = (0, 4, 1)


class PCProcessManager:
    """Process management operations.

    Parameters
    ----------
    port : PCControlPort
        The active PC-control adapter.
    logger : logging.Logger | None
        Module-scoped logger.
    """

    def __init__(
        self,
        port: PCControlPort,
        logger: logging.Logger | None = None,
    ) -> None:
        self._port = port
        self._logger = logger or _LOG

    async def list_processes(self) -> list[ProcessInfo]:
        return await self._port.process_list()

    async def kill_process(self, pid: int, force: bool = False) -> None:
        if pid in CRITICAL_SYSTEM_PIDS:
            raise PermissionError(f"Termination of critical system process PID {pid} is blocked by safety layer.")
        await self._port.process_kill(pid, force=force)

    async def safe_kill_process(self, pid: int | None = None, name: str | None = None, force: bool = False) -> str:
        """Safely terminate a background process by PID or name, protecting system processes."""
        if pid is not None:
            if pid in CRITICAL_SYSTEM_PIDS:
                raise PermissionError(f"Termination of critical system process PID {pid} is blocked by safety layer.")
            await self._port.process_kill(pid, force=force)
            return f"Successfully terminated process PID {pid}."

        if name:
            clean_name = name.strip().lower()
            if any(sys_p in clean_name for sys_p in CRITICAL_SYSTEM_PROCESSES):
                raise PermissionError(f"Termination of system process '{name}' is blocked by safety layer.")

            procs = await self.list_processes()
            matched = [p for p in procs if clean_name in p.name.lower()]
            if not matched:
                return f"No running process found matching name '{name}'."

            killed_count = 0
            for p in matched:
                if p.pid not in CRITICAL_SYSTEM_PIDS:
                    try:
                        await self._port.process_kill(p.pid, force=force)
                        killed_count += 1
                    except Exception as e:
                        self._logger.warning("Failed to kill process PID %d: %s", p.pid, e)
            return f"Successfully terminated {killed_count} process(es) matching '{name}'."

        return "Please specify a PID or process name to terminate."

    async def get_system_metrics(self) -> Any:
        return await self._port.get_system_metrics()

    async def get_open_ports(self) -> list[int]:
        return await self._port.get_open_ports()
