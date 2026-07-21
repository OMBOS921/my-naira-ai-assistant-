"""PC Control volume management — placeholder component.

Provides volume control operations delegated to the port adapter.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.modules.pc_control._types import VolumeInfo
    from backend.modules.pc_control.ports.pc_control_port import PCControlPort

_LOG = logging.getLogger("naira.pc_control.volume")


class PCVolume:
    """System volume control operations.

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

    async def get_volume(self) -> VolumeInfo:
        return await self._port.volume_get()

    async def set_volume(self, level: float) -> None:
        await self._port.volume_set(level)

    async def mute(self, muted: bool = True) -> None:
        await self._port.volume_mute(muted)

    async def unmute(self) -> None:
        await self._port.volume_mute(False)
