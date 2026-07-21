"""
ConversationState — session-level Finite State Machine.

07_Module_Design.md §2.A — FSM pattern.
"""

from __future__ import annotations

from enum import StrEnum


class ConversationState(StrEnum):
    """Session-level FSM states for a single conversation.

    ACTIVE — session is live and processing requests.
    IDLE — session exists but has no recent activity.
    PROCESSING — a request is currently being handled.
    TIMEOUT — session exceeded its idle timeout.
    CLOSED — session has been explicitly closed.
    """

    ACTIVE = "ACTIVE"
    IDLE = "IDLE"
    PROCESSING = "PROCESSING"
    TIMEOUT = "TIMEOUT"
    CLOSED = "CLOSED"
