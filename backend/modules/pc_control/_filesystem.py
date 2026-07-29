"""PC Control filesystem operations — placeholder component.

Provides filesystem read/write operations delegated to the port adapter.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.modules.pc_control._types import FileEntry, FileOpResult
    from backend.modules.pc_control.ports.pc_control_port import PCControlPort

_LOG = logging.getLogger("naira.pc_control.filesystem")


class PCFilesystem:
    """Filesystem access operations.

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

    async def list_directory(self, path: str) -> list[FileEntry]:
        return await self._port.filesystem_list_directory(path)

    async def read_file(self, path: str, encoding: str = "utf-8") -> str:
        return await self._port.filesystem_read_file(path, encoding=encoding)

    async def write_file(self, path: str, content: str, encoding: str = "utf-8") -> FileOpResult:
        return await self._port.filesystem_write_file(path, content, encoding=encoding)

    async def delete_file(self, path: str) -> None:
        await self._port.filesystem_delete_file(path)

    async def create_directory(self, path: str) -> FileOpResult:
        return await self._port.filesystem_create_directory(path)

    async def delete_directory(self, path: str, recursive: bool = False) -> None:
        await self._port.filesystem_delete_directory(path, recursive=recursive)
