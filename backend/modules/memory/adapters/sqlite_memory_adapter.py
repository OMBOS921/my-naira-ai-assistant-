from typing import Any
"""
SQLiteMemoryAdapter — implements ``MemoryPort`` for SQLite persistence.

21_System_Contracts.md §16.2 — MemoryPort interface.
20_Dependency_Rules.md §2 — Port/Adapter pattern.

This adapter is instantiated at boot time (Step 9) and injected into
the Any Manager (Layer 3 — AI Core).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from backend.modules.context.ports.memory_port import MemoryPort
from backend.modules.memory.sqlite_store import SQLiteStore
from backend.types import Message
if TYPE_CHECKING:
    from backend.modules.memory.engines.timeline_engine import TimelineEngine
    from backend.modules.memory.engines.user_profile_engine import UserProfileEngine


class SQLiteMemoryAdapter(MemoryPort):
    """Adapter that exposes a ``SQLiteStore`` through the ``MemoryPort`` interface.

    All public methods are async; synchronous SQLite calls are offloaded
    via ``asyncio.to_thread()``.

    Parameters
    ----------
    store : SQLiteStore
        The underlying synchronous SQLite store.
    timeline_engine : TimelineEngine | None
        Optional TimelineEngine instance for event tracking.
    user_profile_engine : UserProfileEngine | None
        Optional UserProfileEngine instance for profile preferences.
    """

    def __init__(
        self,
        store: SQLiteStore,
        timeline_engine: TimelineEngine | None = None,
        user_profile_engine: UserProfileEngine | None = None,
    ) -> None:
        self._store = store
        self._timeline_engine = timeline_engine
        self._user_profile_engine = user_profile_engine

    def set_engines(
        self,
        timeline_engine: TimelineEngine | None = None,
        user_profile_engine: UserProfileEngine | None = None,
    ) -> None:
        """Attach persistent memory engines post-construction if needed."""
        if timeline_engine is not None:
            self._timeline_engine = timeline_engine
        if user_profile_engine is not None:
            self._user_profile_engine = user_profile_engine

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

    async def get_dynamic_context_summary(
        self, session_id: str = "default", limit_events: int = 3
    ) -> str:
        """Retrieve formatted user profile & top N recent timeline events."""
        parts: list[str] = []

        if self._user_profile_engine is not None:
            prof_summary = await asyncio.to_thread(
                self._user_profile_engine.get_summary_for_prompt
            )
            if prof_summary:
                parts.append(prof_summary)

        if self._timeline_engine is not None:
            tl_summary = await asyncio.to_thread(
                self._timeline_engine.get_summary_for_prompt, limit_events
            )
            if tl_summary:
                parts.append(tl_summary)

        return "\n\n".join(parts)

    async def record_event(
        self,
        event_type: str,
        title: str,
        description: str | None = None,
        session_id: str | None = None,
        importance: int = 5,
        metadata: dict[str, Any] | None = None,
    ) -> int | None:
        """Record a timeline event asynchronously."""
        if self._timeline_engine is None:
            return None
        return await asyncio.to_thread(
            self._timeline_engine.record,
            event_type,
            title,
            description,
            session_id,
            None,
            None,
            importance,
            metadata,
        )

    async def set_user_profile(self, key: str, value: object) -> bool:
        """Set a user profile preference asynchronously."""
        if self._user_profile_engine is None:
            return False
        return await asyncio.to_thread(self._user_profile_engine.set, key, value)

    async def get_user_profile(self, key: str | None = None) -> Any:
        """Get user profile entry or full profile asynchronously."""
        if self._user_profile_engine is None:
            return {} if key is None else None
        if key is None:
            return await asyncio.to_thread(self._user_profile_engine.get_all)
        return await asyncio.to_thread(self._user_profile_engine.get, key)

