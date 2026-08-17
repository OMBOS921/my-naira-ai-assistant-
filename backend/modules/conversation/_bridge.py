from typing import Any
"""
ConversationMemoryBridge — port/adapter bridge between conversation
and memory modules.

20_Dependency_Rules.md §2 — Port/Adapter pattern.
21_System_Contracts.md §16 — Memory Contracts.
"""

from __future__ import annotations

import logging

from backend.types import Message
_LOG = logging.getLogger("naira.conversation")


class ConversationMemoryBridge:
    """Bridges the conversation module to the MemoryManager for
    persistent storage of conversation history.

    Follows the same Port/Adapter pattern used by ``context.MemoryPort``:
    the consumer (conversation) defines the interface, and the provider
    (memory) is injected at boot time.

    Parameters
    ----------
    memory_manager : Any | None
        A ``MemoryManager`` instance injected at boot.  If ``None``,
        the bridge operates in degraded mode (no persistence).
    logger : logging.Logger | None
        Module-scoped logger.
    """

    def __init__(
        self,
        memory_manager: object | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._memory = memory_manager
        self._logger = logger or _LOG

    @property
    def available(self) -> bool:
        """Return ``True`` if the underlying MemoryManager is available."""
        return self._memory is not None

    async def store_message(self, session_id: str, message: Message) -> None:
        """Persist a single message.

        Parameters
        ----------
        session_id : str
            Active session identifier.
        message : Message
            The message to persist.

        Raises
        ------
        RuntimeError
            If no MemoryManager is configured.
        """
        self._ensure_available()
        store = getattr(self._memory, "store_message", None)
        if store is not None:
            await store(session_id, message)

    async def store_messages(
        self, session_id: str, messages: list[Message]
    ) -> None:
        """Persist multiple messages in sequence."""
        self._ensure_available()
        store = getattr(self._memory, "store_message", None)
        if store is not None:
            for msg in messages:
                await store(session_id, msg)

    async def get_history(
        self, session_id: str, limit: int = 50
    ) -> list[Message]:
        """Retrieve conversation history for a session.

        Returns an empty list if no MemoryManager is configured or
        if the session has no stored history.
        """
        if self._memory is None:
            return []
        get_hist = getattr(self._memory, "get_history", None)
        if get_hist is not None:
            return await get_hist(session_id, limit)
        return []

    async def health_check(self) -> bool:
        """Return ``True`` if the backing store is reachable."""
        if self._memory is None:
            return False
        mem_adapter = getattr(self._memory, "memory_adapter", None)
        if mem_adapter is not None:
            hc = getattr(mem_adapter, "health_check", None)
            if hc is not None:
                return await hc()
        return True

    def _ensure_available(self) -> None:
        if self._memory is None:
            raise RuntimeError(
                "ConversationMemoryBridge: no MemoryManager configured"
            )
