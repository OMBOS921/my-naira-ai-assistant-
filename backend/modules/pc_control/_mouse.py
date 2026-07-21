"""PC Control mouse operations — placeholder component.

Provides high-level mouse operations delegated to the port adapter.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.modules.pc_control._types import Point
    from backend.modules.pc_control.ports.pc_control_port import PCControlPort

_LOG = logging.getLogger("naira.pc_control.mouse")


class PCMouse:
    """Mouse control operations.

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

    async def get_position(self) -> Point:
        return await self._port.mouse_get_position()

    async def move_to(self, x: int, y: int, duration: float = 0.0) -> None:
        await self._port.mouse_move_to(x, y, duration=duration)

    async def click(self, x: int | None = None, y: int | None = None) -> None:
        await self._port.mouse_click(x=x, y=y)

    async def double_click(self, x: int | None = None, y: int | None = None) -> None:
        await self._port.mouse_double_click(x=x, y=y)

    async def right_click(self, x: int | None = None, y: int | None = None) -> None:
        await self._port.mouse_right_click(x=x, y=y)

    async def drag(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration: float = 0.5,
    ) -> None:
        await self._port.mouse_drag(start_x, start_y, end_x, end_y, duration=duration)

    async def scroll(self, clicks: int, x: int | None = None, y: int | None = None) -> None:
        await self._port.mouse_scroll(clicks, x=x, y=y)
