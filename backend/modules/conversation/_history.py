from typing import Any
"""
ConversationHistory — manages message history with context merging.

19_Request_Lifecycle.md §3 — Phase 3: Any Assembly.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.modules.conversation._bridge import ConversationMemoryBridge
from backend.types import Message
if TYPE_CHECKING:
    from collections.abc import Sequence

_LOG = logging.getLogger("naira.conversation")


class ConversationHistory:
    """Manages conversation history merging between in-memory sessions
    and persistent storage.

    Responsible for:
    - Loading persistent history via ``ConversationMemoryBridge``.
    - Merging persistent history with current in-memory context.
    - Deduplication of overlapping messages.
    - Token-aware sliding window for context assembly.

    Parameters
    ----------
    bridge : ConversationMemoryBridge
        The persistence bridge to use for loading/saving history.
    logger : logging.Logger | None
        Module-scoped logger.
    max_tokens : int
        Token budget for sliding-window truncation (default 4096).
    """

    def __init__(
        self,
        bridge: ConversationMemoryBridge,
        logger: logging.Logger | None = None,
        max_tokens: int = 4096,
    ) -> None:
        self._bridge = bridge
        self._logger = logger or _LOG
        self._max_tokens = max_tokens

    async def load_persistent_history(
        self, session_id: str, limit: int = 100
    ) -> list[Message]:
        """Load conversation history from persistent storage.

        Parameters
        ----------
        session_id : str
            Session to load history for.
        limit : int
            Maximum number of messages to load.

        Returns
        -------
        list[Message]
            The loaded message history (oldest first).
        """
        return await self._bridge.get_history(session_id, limit)

    def merge_context(
        self,
        persistent: Sequence[Message],
        current: Sequence[Message],
    ) -> list[Message]:
        """Merge persistent history with current in-memory messages.

        The merge algorithm:
        1. Start with persistent messages (oldest first).
        2. Append current in-memory messages.
        3. Remove duplicates (same role + content within a sliding
           window of recent messages).
        4. Apply sliding window if the token budget is exceeded.

        Parameters
        ----------
        persistent : Sequence[Message]
            Messages loaded from persistent storage.
        current : Sequence[Message]
            Messages currently in the in-memory session.

        Returns
        -------
        list[Message]
            Merged and deduplicated message list.
        """
        merged = list(persistent) + list(current)
        merged = self._deduplicate(merged)
        merged = self._apply_sliding_window(merged)
        return merged

    def merge_with_persistent(
        self,
        current: list[Message],
        persistent: list[Message],
    ) -> list[Message]:
        """Alias for ``merge_context`` with swapped parameter order
        for API clarity.

        Callers can use the more natural order:
        ``merge_with_persistent(current_messages, persistent_history)``.
        """
        return self.merge_context(persistent, current)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _deduplicate(messages: list[Message]) -> list[Message]:
        """Remove consecutive duplicate messages.

        A duplicate is defined as a message with the same ``role``
        and ``content`` as the previous message.
        """
        if not messages:
            return []

        deduped: list[Message] = [messages[0]]
        for msg in messages[1:]:
            prev = deduped[-1]
            if not (msg.role == prev.role and msg.content == prev.content):
                deduped.append(msg)
        return deduped

    def _apply_sliding_window(self, messages: list[Message]) -> list[Message]:
        """Truncate oldest messages until token count ≤ max_tokens.

        Guarantees at least one message remains, even if that single
        message exceeds the token budget.
        """
        while (
            self._count_tokens(messages) > self._max_tokens
            and len(messages) > 1
        ):
            messages.pop(0)
        return messages

    def _count_tokens(self, messages: list[Message]) -> int:
        """Estimate total token count for a list of messages."""
        return sum(self._estimate_tokens(msg.content) + 4 for msg in messages)

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token count estimation (~4 characters per token)."""
        return max(1, len(text) // 4)
