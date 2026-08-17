from typing import Any
"""
ConversationContext — in-memory conversation history for one session.

21_System_Contracts.md §16 — Memory Contracts.
19_Request_Lifecycle.md §3 — Phase 3: Any Assembly.

No database persistence.  All state lives in the instance for the
duration of the current session.
"""

from __future__ import annotations

import logging

from backend.types import Message
_LOG = logging.getLogger("naira.context")


class ConversationContext:
    """In-memory conversation history for a single session.

    Manages a list of ``Message`` objects within a configurable
    token budget.  Provides a sliding window that drops the oldest
    messages when the budget is exceeded.

    Parameters
    ----------
    session_id : str
        Unique identifier for this conversation session.
    max_tokens : int
        Maximum total tokens allowed before the sliding window
        truncates history.
    """

    def __init__(self, session_id: str, max_tokens: int = 4096) -> None:
        self._session_id = session_id
        self._max_tokens = max_tokens
        self._messages: list[Message] = []

    # ------------------------------------------------------------------
    # Read-only properties
    # ------------------------------------------------------------------

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def max_tokens(self) -> int:
        return self._max_tokens

    @max_tokens.setter
    def max_tokens(self, value: int) -> None:
        self._max_tokens = value

    @property
    def messages(self) -> list[Message]:
        return list(self._messages)

    @property
    def message_count(self) -> int:
        return len(self._messages)

    @property
    def token_count(self) -> int:
        """Estimated token count across all messages.

        Uses a simple 4-char-per-token heuristic plus 4 tokens of
        overhead per message.
        """
        return sum(self._estimate_tokens(msg.content) + 4 for msg in self._messages)

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_message(self, message: Message) -> None:
        """Append a ``Message`` to the history."""
        self._messages.append(message)

    def add_user_message(self, content: str) -> Message:
        """Convenience: create and append a user ``Message``."""
        msg = Message(role="user", content=content)
        self.add_message(msg)
        return msg

    def add_assistant_message(self, content: str) -> Message:
        """Convenience: create and append an assistant ``Message``."""
        msg = Message(role="assistant", content=content)
        self.add_message(msg)
        return msg

    def add_system_message(self, content: str) -> Message:
        """Convenience: create and append a system ``Message``."""
        msg = Message(role="system", content=content)
        self.add_message(msg)
        return msg

    def apply_sliding_window(self) -> None:
        """Truncate oldest messages until token count ≤ max_tokens.

        19_Request_Lifecycle.md §3 Step 3.

        Guarantees at least one message remains in the history,
        even if that single message exceeds the token budget.
        """
        while self.token_count > self._max_tokens and len(self._messages) > 1:
            removed = self._messages.pop(0)
            _LOG.debug(
                "Sliding window dropped %s message — session=%s",
                removed.role,
                self._session_id,
            )

    def get_recent_messages(self, limit: int = 10) -> list[Message]:
        """Return the most recent *limit* messages."""
        return self._messages[-limit:]

    def clear(self) -> None:
        """Remove all messages from the session."""
        self._messages.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token count estimation (~4 characters per token)."""
        return max(1, len(text) // 4)
