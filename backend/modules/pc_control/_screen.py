"""PC Control screen / display operations — placeholder component.

Provides screen capture and display information operations delegated
to the port adapter.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.modules.pc_control._types import DisplayInfo, ScreenshotResult, ScreenSize
    from backend.modules.pc_control.ports.pc_control_port import PCControlPort

_LOG = logging.getLogger("naira.pc_control.screen")


class PCScreen:
    """Screen and display operations.

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

    async def get_size(self) -> ScreenSize:
        return await self._port.screen_get_size()

    async def capture(
        self,
        region: tuple[int, int, int, int] | None = None,
        save_path: str | None = None,
    ) -> ScreenshotResult:
        return await self._port.screen_capture(region=region, save_path=save_path)

    async def list_displays(self) -> list[DisplayInfo]:
        return await self._port.screen_list_displays()
