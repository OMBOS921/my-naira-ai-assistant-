"""
MemoryPort — abstract interface for long-term memory operations.

21_System_Contracts.md §16.2 — MemoryPort interface.
20_Dependency_Rules.md §2 — Port/Adapter pattern.

Implemented by ``memory.SQLiteMemoryAdapter`` (Layer 5 — Infrastructure).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.types import Message


class MemoryPort(ABC):
    """Port for long-term memory persistence.

    The ``context/`` module (Layer 3 — AI Core) depends on this port
    to load and store conversation history.  The concrete adapter is
    provided by ``memory/`` (Layer 5 — Infrastructure) at boot time.
    """

    @abstractmethod
    async def store_message(self, session_id: str, message: Message) -> None:
        """Persist a single message."""
        ...

    @abstractmethod
    async def get_history(self, session_id: str, limit: int = 50) -> list[Message]:
        """Retrieve recent messages for a session."""
        ...

    @abstractmethod
    async def store_setting(self, key: str, value: object) -> None:
        """Persist a key-value setting."""
        ...

    @abstractmethod
    async def get_setting(self, key: str) -> object | None:
        """Retrieve a previously stored setting."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Return ``True`` if the backing store is reachable."""
        ...

    async def get_dynamic_context_summary(
        self, session_id: str = "default", limit_events: int = 3
    ) -> str:
        """Retrieve dynamic historical context string (user profile + recent timeline events)."""
        return ""

    async def record_event(
        self,
        event_type: str,
        title: str,
        description: str | None = None,
        session_id: str | None = None,
        importance: int = 5,
        metadata: dict | None = None,
    ) -> int | None:
        """Record a temporal or milestone event."""
        return None

    async def set_user_profile(self, key: str, value: object) -> bool:
        """Set a user profile preference."""
        return False

    async def get_user_profile(self, key: str | None = None) -> object:
        """Get user profile preference or full profile dict."""
        return {} if key is None else None

