from __future__ import annotations

import logging
from pathlib import Path

from backend.modules.coding_agent._exceptions import FileOperationError
from backend.modules.coding_agent.ports.file_manager_port import FileManagerPort

_LOG = logging.getLogger("naira.coding_agent.file_manager")


class OSFileManagerProvider(FileManagerPort):
    """Default provider for the File Manager port.

    Provides safe file operations using the OS filesystem.
    """

    def __init__(
        self,
        *,
        allowed_paths: tuple[str, ...] | None = None,
        max_file_size: int = 1_048_576,
        logger: logging.Logger | None = None,
    ) -> None:
        self._logger = logger or _LOG
        self._available: bool = True
        self._allowed_paths = tuple(Path(p).resolve() for p in (allowed_paths or ()))
        self._max_file_size = max_file_size

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def provider_name(self) -> str:
        return "os_file_manager"

    async def read_file(
        self,
        path: str,
        encoding: str = "utf-8",
    ) -> str:
        try:
            resolved = self._resolve_path(path)
            content = resolved.read_text(encoding=encoding)
            if len(content) > self._max_file_size:
                raise FileOperationError(
                    f"File too large: {path} ({len(content)} > {self._max_file_size})",
                )
            return content
        except FileOperationError:
            raise
        except Exception as exc:
            raise FileOperationError(f"Failed to read file {path}: {exc}") from exc

    async def write_file(
        self,
        path: str,
        content: str,
        encoding: str = "utf-8",
    ) -> None:
        try:
            resolved = self._resolve_path(path)
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(content, encoding=encoding)
            self._logger.debug("Wrote file: %s (%d bytes)", resolved, len(content))
        except Exception as exc:
            raise FileOperationError(f"Failed to write file {path}: {exc}") from exc

    async def create_file(
        self,
        path: str,
        content: str = "",
        encoding: str = "utf-8",
    ) -> None:
        await self.write_file(path, content, encoding)

    async def delete_file(
        self,
        path: str,
    ) -> None:
        try:
            resolved = self._resolve_path(path)
            if resolved.exists():
                resolved.unlink()
                self._logger.debug("Deleted file: %s", resolved)
        except Exception as exc:
            raise FileOperationError(f"Failed to delete file {path}: {exc}") from exc

    async def list_directory(
        self,
        path: str,
        recursive: bool = False,
    ) -> list[str]:
        try:
            resolved = self._resolve_path(path)
            if not resolved.is_dir():
                raise FileOperationError(f"Not a directory: {path}")
            if recursive:
                files = [str(p) for p in resolved.rglob("*") if p.is_file()]
            else:
                files = [str(p) for p in resolved.iterdir() if p.is_file()]
            return sorted(files)
        except FileOperationError:
            raise
        except Exception as exc:
            raise FileOperationError(f"Failed to list directory {path}: {exc}") from exc

    async def file_exists(
        self,
        path: str,
    ) -> bool:
        try:
            resolved = self._resolve_path(path)
            return resolved.exists() and resolved.is_file()
        except Exception:
            return False

    async def close(self) -> None:
        self._available = False
        self._logger.info("File manager provider closed")

    def _resolve_path(self, path: str) -> Path:
        resolved = Path(path).resolve()
        if self._allowed_paths and not any(
            resolved == allowed or str(resolved).startswith(str(allowed) + "\\")
            for allowed in self._allowed_paths
        ):
            raise FileOperationError(
                f"Path not allowed: {path} (restricted to {self._allowed_paths})",
            )
        return resolved
