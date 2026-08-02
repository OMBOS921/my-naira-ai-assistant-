"""
BrowserDownloader — helper for managing sandboxed file downloads.

21_System_Contracts.md §18 — Security and sandbox path constraints.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from backend.modules.browser._exceptions import BrowserDownloadError, BrowserPermissionError
from backend.modules.browser._types import DownloadResult
from backend.modules.security._path_validator import PathValidator

_LOG = logging.getLogger("naira.browser.downloads")


class BrowserDownloader:
    """Manager for browser file downloads with path sandboxing.

    Parameters
    ----------
    download_dir : str | None
        Directory where downloads will be stored. Defaults to
        ``<cwd>/data/downloads``.
    logger : logging.Logger | None
        Module-scoped logger.
    """

    def __init__(
        self,
        download_dir: str | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._logger = logger or _LOG
        if download_dir:
            self._download_dir = Path(download_dir).resolve()
        else:
            self._download_dir = (Path.cwd() / "data" / "downloads").resolve()
        self._download_dir.mkdir(parents=True, exist_ok=True)
        self._path_validator = PathValidator()

    @property
    def download_dir(self) -> Path:
        """Return the active download directory."""
        return self._download_dir

    async def validate_path(self, target_path: str) -> None:
        """Validate that target_path is allowed under sandbox policy."""
        check = await self._path_validator.validate(target_path)
        if getattr(check, "denied", False):
            reason = getattr(check, "reason", "Path blocked by sandbox")
            raise BrowserPermissionError(
                f"Download target path '{target_path}' is denied: {reason}",
                context={"path": target_path},
            )

    def prepare_target_file(self, filename: str) -> Path:
        """Construct and validate a safe target filepath in the download dir."""
        safe_name = Path(filename).name or "download.dat"
        target = (self._download_dir / safe_name).resolve()
        try:
            target.relative_to(self._download_dir)
        except ValueError as exc:
            raise BrowserDownloadError(
                f"Directory traversal detected in filename '{filename}'",
                context={"filename": filename},
            ) from exc
        return target
