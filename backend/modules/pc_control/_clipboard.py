"""PC Control clipboard operations — placeholder component.

Provides clipboard read/write operations delegated to the port adapter.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.modules.pc_control._types import ClipboardContent
    from backend.modules.pc_control.ports.pc_control_port import PCControlPort

_LOG = logging.getLogger("naira.pc_control.clipboard")


class PCClipboard:
    """Clipboard access operations.

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

    async def get_text(self) -> ClipboardContent:
        return await self._port.clipboard_get_text()

    async def set_text(self, text: str) -> None:
        await self._port.clipboard_set_text(text)

    async def clear(self) -> None:
        await self._port.clipboard_clear()
