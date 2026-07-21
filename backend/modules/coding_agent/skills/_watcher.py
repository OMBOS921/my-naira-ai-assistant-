"""
SkillWatcher — hot-reload support for Skill Packs.

Monitors the skills pack directory for file changes and triggers
hot-reload of changed skill pack modules at runtime.
"""

from __future__ import annotations

import logging
from pathlib import Path

_LOG = logging.getLogger("naira.coding_agent.skills.watcher")


class SkillWatcher:
    """Watch skill pack files for changes and hot-reload them.

    Parameters
    ----------
    watch_dir : str | Path | None
        Directory to watch for skill pack files.
    poll_interval : float
        How often to check for changes (seconds).
    """

    def __init__(
        self,
        *,
        watch_dir: str | Path | None = None,
        poll_interval: float = 2.0,
        logger: logging.Logger | None = None,
    ) -> None:
        self._watch_dir = Path(watch_dir) if watch_dir else self._default_watch_dir()
        self._poll_interval = poll_interval
        self._logger = logger or _LOG
        self._file_mtimes: dict[str, float] = {}
        self._running = False
        self._enabled = False

    @staticmethod
    def _default_watch_dir() -> Path:
        base = Path(__file__).resolve().parent / "packs"
        return base if base.is_dir() else Path.cwd()

    def enable(self) -> None:
        """Enable hot-reload watching."""
        self._enabled = True
        self._scan_initial_mtimes()
        self._logger.info(
            "SkillWatcher enabled — watching %s (poll=%ss)",
            self._watch_dir,
            self._poll_interval,
        )

    def disable(self) -> None:
        """Disable hot-reload watching."""
        self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _scan_initial_mtimes(self) -> None:
        if not self._watch_dir.is_dir():
            return
        for entry in self._watch_dir.iterdir():
            if entry.suffix == ".py" and entry.is_file():
                self._file_mtimes[str(entry)] = entry.stat().st_mtime

    def check_changes(self) -> list[str]:
        """Check for changed skill pack files.

        Returns
        -------
        list[str]
            Names of changed files (stem only).
        """
        if not self._enabled or not self._watch_dir.is_dir():
            return []

        changed: list[str] = []
        for entry in self._watch_dir.iterdir():
            if entry.suffix != ".py" or not entry.is_file():
                continue
            key = str(entry)
            current_mtime = entry.stat().st_mtime
            prev_mtime = self._file_mtimes.get(key)

            if prev_mtime is None:
                self._file_mtimes[key] = current_mtime
            elif current_mtime > prev_mtime:
                self._file_mtimes[key] = current_mtime
                changed.append(entry.stem)

        return changed

    def degraded(self) -> bool:
        return not self._enabled
