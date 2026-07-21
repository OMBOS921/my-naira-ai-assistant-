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
        await self._port.process_kill(pid, force=force)
