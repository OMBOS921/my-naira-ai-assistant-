"""
SQLiteMemoryAdapter — implements ``MemoryPort`` for SQLite persistence.

21_System_Contracts.md §16.2 — MemoryPort interface.
20_Dependency_Rules.md §2 — Port/Adapter pattern.

This adapter is instantiated at boot time (Step 9) and injected into
the Context Manager (Layer 3 — AI Core).
"""

from __future__ import annotations

import asyncio

from backend.modules.context.ports.memory_port import MemoryPort
from backend.modules.memory.sqlite_store import SQLiteStore
from backend.types import Message


class SQLiteMemoryAdapter(MemoryPort):
    """Adapter that exposes a ``SQLiteStore`` through the ``MemoryPort`` interface.

    All public methods are async; synchronous SQLite calls are offloaded
    via ``asyncio.to_thread()``.

    Parameters
    ----------
    store : SQLiteStore
        The underlying synchronous SQLite store.
    """

    def __init__(self, store: SQLiteStore) -> None:
        self._store = store

    async def store_message(self, session_id: str, message: Message) -> None:
        await asyncio.to_thread(self._store.store_message, session_id, message)

    async def get_history(
        self, session_id: str, limit: int = 50
    ) -> list[Message]:
        return await asyncio.to_thread(self._store.get_history, session_id, limit)

    async def store_setting(self, key: str, value: object) -> None:
        await asyncio.to_thread(self._store.store_setting, key, value)

    async def get_setting(self, key: str) -> object | None:
        return await asyncio.to_thread(self._store.get_setting, key)

    async def health_check(self) -> bool:
        return await asyncio.to_thread(self._store.health_check)
