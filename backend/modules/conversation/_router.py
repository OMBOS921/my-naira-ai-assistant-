"""
ConversationRouter — multi-session routing and lifecycle management.

19_Request_Lifecycle.md §2 — Phase 2: Session Resolution.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.modules.conversation._session import ConversationSession
from backend.modules.conversation._state import ConversationState

_LOG = logging.getLogger("naira.conversation")


class ConversationRouter:
    """Routes incoming requests to the correct session.

    Manages a collection of ``ConversationSession`` instances keyed
    by ``session_id``.  Handles session creation, retrieval, timeout
    detection, and cleanup.

    Parameters
    ----------
    session_timeout : float
        Default idle timeout in seconds for new sessions (default 300).
    logger : logging.Logger | None
        Module-scoped logger.
    """

    def __init__(
        self,
        session_timeout: float = 300.0,
        logger: logging.Logger | None = None,
    ) -> None:
        self._session_timeout = session_timeout
        self._logger = logger or _LOG
        self._sessions: dict[str, ConversationSession] = {}

    def route(self, session_id: str) -> ConversationSession:
        """Route a request to the appropriate session.

        Returns the existing session if one exists, or creates a new
        one if not.

        Parameters
        ----------
        session_id : str
            The session identifier from the incoming request.

        Returns
        -------
        ConversationSession
            The resolved (existing or new) session.
        """
        session = self._sessions.get(session_id)
        if session is None:
            session = ConversationSession(
                session_id=session_id,
                timeout_seconds=self._session_timeout,
            )
            self._sessions[session_id] = session
            self._logger.debug("Created session: %s", session_id)
        else:
            if not session.is_active:
                self._logger.debug(
                    "Reviving inactive session: %s (state=%s)",
                    session_id,
                    session.state,
                )
                session.state = ConversationState.ACTIVE
        session.touch()
        return session

    def get_session(self, session_id: str) -> ConversationSession | None:
        """Retrieve a session without creating it.

        Returns ``None`` if the session does not exist.
        """
        return self._sessions.get(session_id)

    def has_session(self, session_id: str) -> bool:
        """Return ``True`` if a session with the given ID exists."""
        return session_id in self._sessions

    async def close_session(self, session_id: str) -> None:
        """Close a session and transition it to CLOSED state.

        The session remains in the registry but is marked as closed.
        """
        session = self._sessions.get(session_id)
        if session is not None:
            session.state = ConversationState.CLOSED
            self._logger.info("Session closed: %s", session_id)

    def remove_session(self, session_id: str) -> None:
        """Remove a session entirely from the registry."""
        self._sessions.pop(session_id, None)
        self._logger.debug("Session removed: %s", session_id)

    def cleanup_expired(self) -> list[str]:
        """Find and mark all expired sessions as TIMEOUT.

        Returns
        -------
        list[str]
            List of session IDs that were marked as timed out.
        """
        timed_out: list[str] = []
        for session_id, session in list(self._sessions.items()):
            if session.is_expired and session.is_active:
                session.state = ConversationState.TIMEOUT
                timed_out.append(session_id)
                self._logger.info("Session timed out: %s", session_id)
        return timed_out

    def purge_closed(self) -> list[str]:
        """Remove all closed sessions from the registry.

        Returns
        -------
        list[str]
            List of purged session IDs.
        """
        purged: list[str] = []
        self._sessions = {
            sid: s
            for sid, s in self._sessions.items()
            if s.state != ConversationState.CLOSED
        }
        return purged

    @property
    def active_sessions(self) -> list[str]:
        """Return IDs of all non-closed, non-timed-out sessions."""
        return [
            sid
            for sid, s in self._sessions.items()
            if s.state not in (ConversationState.CLOSED, ConversationState.TIMEOUT)
        ]

    @property
    def all_sessions(self) -> list[str]:
        """Return IDs of all sessions in the registry."""
        return list(self._sessions.keys())

    @property
    def session_count(self) -> int:
        """Return the total number of tracked sessions."""
        return len(self._sessions)

    def get_session_data(self, session_id: str) -> dict[str, Any] | None:
        """Return session metadata dict, or ``None`` if not found."""
        session = self._sessions.get(session_id)
        if session is None:
            return None
        return dict(session.metadata)
