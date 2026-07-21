"""PC Control window management operations — placeholder component.

Provides window listing and manipulation operations delegated to
the port adapter.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.modules.pc_control._types import WindowInfo
    from backend.modules.pc_control.ports.pc_control_port import PCControlPort

_LOG = logging.getLogger("naira.pc_control.window")


class PCWindowManager:
    """Window management operations.

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

    async def list_windows(self) -> list[WindowInfo]:
        return await self._port.window_list()

    async def get_active_window(self) -> WindowInfo | None:
        return await self._port.window_get_active()

    async def focus(self, handle: int) -> None:
        await self._port.window_focus(handle)

    async def minimize(self, handle: int) -> None:
        await self._port.window_minimize(handle)

    async def maximize(self, handle: int) -> None:
        await self._port.window_maximize(handle)

    async def close(self, handle: int) -> None:
        await self._port.window_close(handle)

    async def resize(self, handle: int, width: int, height: int) -> None:
        await self._port.window_resize(handle, width, height)

    async def move(self, handle: int, x: int, y: int) -> None:
        await self._port.window_move(handle, x, y)
