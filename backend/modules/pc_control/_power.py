"""PC Control power management — placeholder component.

Provides power operations delegated to the port adapter.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.modules.pc_control.ports.pc_control_port import PCControlPort

_LOG = logging.getLogger("naira.pc_control.power")


class PCPower:
    """System power management operations.

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

    async def shutdown(self) -> None:
        await self._port.power_shutdown()

    async def restart(self) -> None:
        await self._port.power_restart()

    async def sleep(self) -> None:
        await self._port.power_sleep()

    async def hibernate(self) -> None:
        await self._port.power_hibernate()

    async def lock(self) -> None:
        await self._port.power_lock()
