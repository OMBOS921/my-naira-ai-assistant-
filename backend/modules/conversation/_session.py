"""
ConversationSession — per-session state container with timeout tracking.

19_Request_Lifecycle.md §1 — Session data model.
21_System_Contracts.md §4.2 — ModuleInterface protocol.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from backend.modules.conversation._state import ConversationState


@dataclass
class ConversationSession:
    """Mutable container for a single conversation session.

    Tracks session-level FSM state, activity timestamps for idle
    timeout detection, and message count for statistics.

    Parameters
    ----------
    session_id : str
        Unique session identifier.
    state : ConversationState
        Current FSM state (default ``ACTIVE``).
    last_activity : float
        Unix timestamp of the last interaction (default ``time.time()``).
    created_at : float
        Unix timestamp of session creation (default ``time.time()``).
    timeout_seconds : float
        Idle timeout in seconds (default 300).
    message_count : int
        Total messages exchanged in this session.
    metadata : dict[str, Any]
        Extensible bag for custom session data.
    """

    session_id: str
    state: ConversationState = ConversationState.ACTIVE
    last_activity: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)
    timeout_seconds: float = 300.0
    message_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        """Refresh the activity timestamp and transition to ACTIVE."""
        self.last_activity = time.time()
        if self.state in (ConversationState.IDLE, ConversationState.ACTIVE):
            self.state = ConversationState.ACTIVE

    @property
    def is_expired(self) -> bool:
        """Return ``True`` if the session has exceeded its idle timeout
        or has been closed.

        A session in CLOSED state is always considered expired.
        """
        if self.state == ConversationState.CLOSED:
            return True
        if self.state == ConversationState.TIMEOUT:
            return True
        return time.time() - self.last_activity > self.timeout_seconds

    @property
    def idle_duration(self) -> float:
        """Return the number of seconds since the last activity."""
        return time.time() - self.last_activity

    @property
    def is_active(self) -> bool:
        """Return ``True`` if the session can accept new requests."""
        return self.state not in (ConversationState.TIMEOUT, ConversationState.CLOSED)
