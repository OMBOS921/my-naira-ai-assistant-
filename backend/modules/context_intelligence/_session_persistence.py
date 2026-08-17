"""Session Persistence — persists and restores session state.

Enables saving and loading of session context across restarts,
supporting both in-memory and file-backed persistence.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_LOG = logging.getLogger("naira.context_intelligence.session_persistence")

_SESSION_VERSION = 1


@dataclass
class SessionState:
    """State data for a single session."""

    session_id: str
    created_at: float
    updated_at: float
    metadata: dict[str, Any] = field(default_factory=dict)
    context_data: dict[str, Any] = field(default_factory=dict)
    state_data: dict[str, Any] = field(default_factory=dict)


class SessionPersistence:
    """Manages session persistence for the Any Intelligence layer.

    Parameters
    ----------
    logger : logging.Logger | None
        Module-scoped logger.
    persist_dir : Path | str | None
        Directory for persisting session data.
    """

    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
        persist_dir: Path | str | None = None,
    ) -> None:
        self._logger = logger or _LOG
        self._persist_dir = Path(persist_dir) if persist_dir else Path.cwd() / ".ci_sessions"
        self._sessions: dict[str, SessionState] = {}
        self._total_persisted = 0
        self._total_restored = 0

    def create_session(
        self, session_id: str, metadata: dict[str, Any] | None = None
    ) -> SessionState:
        """Create a new session state.

        Parameters
        ----------
        session_id : str
            Unique session identifier.
        metadata : dict[str, Any] | None
            Optional session metadata.

        Returns
        -------
        SessionState
            The newly created session state.
        """
        now = time.time()
        state = SessionState(
            session_id=session_id,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )
        self._sessions[session_id] = state
        self._logger.debug("Created session: %s", session_id)
        return state

    def get_session(self, session_id: str) -> SessionState | None:
        """Retrieve a session state.

        Parameters
        ----------
        session_id : str
            Session identifier.

        Returns
        -------
        SessionState | None
            Session state if found.
        """
        return self._sessions.get(session_id)

    def update_session(
        self,
        session_id: str,
        context_data: dict[str, Any] | None = None,
        state_data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SessionState | None:
        """Update an existing session state.

        Parameters
        ----------
        session_id : str
            Session identifier.
        context_data : dict[str, Any] | None
            Any data to merge.
        state_data : dict[str, Any] | None
            State data to merge.
        metadata : dict[str, Any] | None
            Metadata to merge.

        Returns
        -------
        SessionState | None
            Updated session state if session exists.
        """
        state = self._sessions.get(session_id)
        if state is None:
            return None

        state.updated_at = time.time()
        if context_data:
            state.context_data.update(context_data)
        if state_data:
            state.state_data.update(state_data)
        if metadata:
            state.metadata.update(metadata)

        return state

    def delete_session(self, session_id: str) -> None:
        """Delete a session state.

        Parameters
        ----------
        session_id : str
            Session identifier.
        """
        self._sessions.pop(session_id, None)
        self._delete_persisted(session_id)
        self._logger.debug("Deleted session: %s", session_id)

    def list_sessions(self) -> list[str]:
        """List all active session IDs.

        Returns
        -------
        list[str]
            Sorted list of session IDs.
        """
        return sorted(self._sessions.keys())

    async def persist_session(self, session_id: str) -> bool:
        """Persist a session state to disk.

        Parameters
        ----------
        session_id : str
            Session identifier.

        Returns
        -------
        bool
            True if persistence succeeded.
        """
        state = self._sessions.get(session_id)
        if state is None:
            return False

        try:
            self._persist_dir.mkdir(parents=True, exist_ok=True)
            file_path = self._persist_dir / f"{session_id}.json"
            data = {
                "version": _SESSION_VERSION,
                "session_id": state.session_id,
                "created_at": state.created_at,
                "updated_at": state.updated_at,
                "metadata": state.metadata,
                "context_data": state.context_data,
                "state_data": state.state_data,
            }
            file_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
            self._total_persisted += 1
            return True
        except OSError as exc:
            self._logger.warning("Failed to persist session %s: %s", session_id, exc)
            return False

    async def restore_session(self, session_id: str) -> SessionState | None:
        """Restore a session state from disk.

        Parameters
        ----------
        session_id : str
            Session identifier.

        Returns
        -------
        SessionState | None
            Restored session state if found.
        """
        file_path = self._persist_dir / f"{session_id}.json"
        if not file_path.exists():
            return None

        try:
            raw = file_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            state = SessionState(
                session_id=data["session_id"],
                created_at=data.get("created_at", time.time()),
                updated_at=data.get("updated_at", time.time()),
                metadata=data.get("metadata", {}),
                context_data=data.get("context_data", {}),
                state_data=data.get("state_data", {}),
            )
            self._sessions[session_id] = state
            self._total_restored += 1
            return state
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            self._logger.warning("Failed to restore session %s: %s", session_id, exc)
            return None

    async def persist_all(self) -> None:
        """Persist all active sessions to disk."""
        for session_id in list(self._sessions.keys()):
            await self.persist_session(session_id)

    def _delete_persisted(self, session_id: str) -> None:
        file_path = self._persist_dir / f"{session_id}.json"
        try:
            if file_path.exists():
                file_path.unlink()
        except OSError:
            pass

    def clear(self) -> None:
        """Clear all in-memory sessions."""
        self._sessions.clear()

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    @property
    def total_persisted(self) -> int:
        return self._total_persisted

    @property
    def total_restored(self) -> int:
        return self._total_restored

    async def health_check(self) -> bool:
        try:
            self._persist_dir.mkdir(parents=True, exist_ok=True)
            return True
        except OSError:
            return False
