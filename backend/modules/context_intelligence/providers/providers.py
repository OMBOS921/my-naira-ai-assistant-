"""Default adapter implementations for Any Intelligence ports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.modules.context_intelligence.ports.ports import MemoryPort


class MemoryAdapter(MemoryPort):
    """Default memory adapter using a JSON file for storage.

    Parameters
    ----------
    storage_path : Path | str
        Path to the JSON storage file.
    """

    def __init__(
        self,
        storage_path: Path | str | None = None,
    ) -> None:
        self._storage_path = Path(storage_path) if storage_path else Path.cwd() / "ci_cache.json"
        self._data: dict[str, Any] = {}
        self._loaded = False

    async def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if self._storage_path.exists():
            try:
                raw = self._storage_path.read_text(encoding="utf-8")
                self._data = json.loads(raw)
            except (json.JSONDecodeError, OSError):
                self._data = {}
        self._loaded = True

    async def _save(self) -> None:
        import contextlib
        with contextlib.suppress(OSError):
            self._storage_path.write_text(
                json.dumps(self._data, indent=2, default=str),
                encoding="utf-8",
            )

    async def store(self, key: str, value: Any) -> None:
        await self._ensure_loaded()
        self._data[key] = value
        await self._save()

    async def load(self, key: str) -> Any | None:
        await self._ensure_loaded()
        return self._data.get(key)

    async def delete(self, key: str) -> None:
        await self._ensure_loaded()
        self._data.pop(key, None)
        await self._save()

    async def list_keys(self, prefix: str) -> list[str]:
        await self._ensure_loaded()
        return [k for k in self._data if k.startswith(prefix)]

    async def health_check(self) -> bool:
        try:
            await self._ensure_loaded()
            return True
        except Exception:
            return False


class DictMemoryAdapter(MemoryPort):
    """In-memory adapter for testing."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def store(self, key: str, value: Any) -> None:
        self._data[key] = value

    async def load(self, key: str) -> Any | None:
        return self._data.get(key)

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)

    async def list_keys(self, prefix: str) -> list[str]:
        return [k for k in self._data if k.startswith(prefix)]

    async def health_check(self) -> bool:
        return True
