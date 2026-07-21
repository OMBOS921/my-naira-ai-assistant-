"""PC Control keyboard operations — placeholder component.

Provides high-level keyboard operations delegated to the port adapter.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.modules.pc_control.ports.pc_control_port import PCControlPort

_LOG = logging.getLogger("naira.pc_control.keyboard")


class PCKeyboard:
    """Keyboard control operations.

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

    async def type_text(self, text: str, interval: float = 0.0) -> None:
        await self._port.keyboard_type_text(text, interval=interval)

    async def press_key(self, key: str) -> None:
        await self._port.keyboard_press_key(key)

    async def hotkey(self, *keys: str) -> None:
        await self._port.keyboard_hotkey(*keys)
