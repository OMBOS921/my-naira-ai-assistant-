"""
SessionManager — manages conversation sessions and state persistence.

Integrates with ConversationManager for session routing and
ContextManager for context persistence.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from backend.modules.context import ContextManager
from backend.modules.conversation import ConversationManager
from backend.orchestrator import EventBus
from backend.types import Message

_LOG = logging.getLogger("naira.runtime.session_manager")


class SessionManager:
    """Manages conversation sessions and their lifecycle.

    Coordinates between ConversationManager (session routing, state)
    and ContextManager (in-memory message history).

    Parameters
    ----------
    conversation_manager : ConversationManager | None
        ConversationManager instance.
    context_manager : ContextManager | None
        ContextManager instance for context persistence.
    event_bus : EventBus | None
        EventBus for event emission.
    logger : logging.Logger | None
        Module-scoped logger.
    session_timeout : float
        Idle timeout in seconds (default 300).
    idle_cleanup_interval : float
        Background cleanup interval in seconds (default 60).
    """

    def __init__(
        self,
        *,
        conversation_manager: ConversationManager | None = None,
        context_manager: ContextManager | None = None,
        event_bus: EventBus | None = None,
        logger: logging.Logger | None = None,
        session_timeout: float = 300.0,
        idle_cleanup_interval: float = 60.0,
    ) -> None:
        self._conversation_manager = conversation_manager
        self._context_manager = context_manager
        self._event_bus = event_bus
        self._logger = logger or _LOG
        self._session_timeout = session_timeout
        self._idle_cleanup_interval = idle_cleanup_interval
        self._degraded: bool = False
        self._initialized: bool = False
        self._cleanup_task: Any = None
        self._global_lock: asyncio.Lock = asyncio.Lock()
        self._session_locks: dict[str, asyncio.Lock] = {}

    async def _get_session_lock(self, session_id: str) -> asyncio.Lock:
        """Safely retrieve or create a per-session lock using global lock synchronization."""
        if session_id not in self._session_locks:
            async with self._global_lock:
                if session_id not in self._session_locks:
                    self._session_locks[session_id] = asyncio.Lock()
        return self._session_locks[session_id]

    # ------------------------------------------------------------------
    # Module lifecycle
    # ------------------------------------------------------------------

    async def async_init(self) -> None:
        """Initialise the session manager."""
        if self._conversation_manager is not None:
            init = getattr(self._conversation_manager, "async_init", None)
            if init is not None:
                await init()

        if self._context_manager is not None:
            init = getattr(self._context_manager, "async_init", None)
            if init is not None:
                await init()

        self._initialized = True
        self._logger.debug("Session manager initialised")

    async def async_shutdown(self) -> None:
        """Release resources and stop cleanup task."""
        self._stop_cleanup_task()

        if self._conversation_manager is not None:
            shutdown = getattr(self._conversation_manager, "async_shutdown", None)
            if shutdown is not None:
                await shutdown()

        if self._context_manager is not None:
            shutdown = getattr(self._context_manager, "async_shutdown", None)
            if shutdown is not None:
                await shutdown()

        self._degraded = False
        self._initialized = False
        self._logger.debug("Session manager shut down")

    def degrade(self) -> None:
        """Mark as degraded."""
        self._stop_cleanup_task()
        self._degraded = True
        if self._conversation_manager is not None:
            degrade = getattr(self._conversation_manager, "degrade", None)
            if degrade is not None:
                degrade()
        if self._context_manager is not None:
            degrade = getattr(self._context_manager, "degrade", None)
            if degrade is not None:
                degrade()
        self._logger.warning("Session manager marked degraded")

    @property
    def degraded(self) -> bool:
        return self._degraded

    @property
    def initialized(self) -> bool:
        return self._initialized

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_or_create_session(self, session_id: str) -> object:
        """Get existing session or create a new one safely.

        Parameters
        ----------
        session_id : str
            Session identifier.

        Returns
        -------
        ConversationSession
            The resolved session.
        """
        self._ensure_not_degraded()

        lock = await self._get_session_lock(session_id)
        async with lock:
            if self._conversation_manager is None:
                return _SimpleSession(session_id=session_id)

            router = getattr(self._conversation_manager, "router", None)
            if router is not None:
                return router.route(session_id)

            return _SimpleSession(session_id=session_id)

    async def close_session(self, session_id: str) -> None:
        """Close a session."""
        self._ensure_not_degraded()

        lock = await self._get_session_lock(session_id)
        async with lock:
            await self._close_session_internal(session_id)

        async with self._global_lock:
            self._session_locks.pop(session_id, None)

    async def _close_session_internal(self, session_id: str) -> None:
        if self._conversation_manager is not None:
            close = getattr(self._conversation_manager, "close_session", None)
            if close is not None:
                await close(session_id)

        if self._context_manager is not None:
            self._context_manager.remove_session(session_id)

        await self._emit_event("runtime.session_closed", {
            "session_id": session_id,
        })

    def remove_session(self, session_id: str) -> None:
        """Remove a session entirely."""
        self._ensure_not_degraded()

        if self._conversation_manager is not None:
            remove = getattr(self._conversation_manager, "remove_session", None)
            if remove is not None:
                remove(session_id)

        if self._context_manager is not None:
            self._context_manager.remove_session(session_id)

    async def update_session(
        self,
        session_id: str,
        user_text: str,
        assistant_text: str,
    ) -> None:
        """Update session with latest conversation turn.

        Persists to both ConversationManager (in-memory) and
        ContextManager (context history).

        Parameters
        ----------
        session_id : str
            Session identifier.
        user_text : str
            User message.
        assistant_text : str
            Assistant response.
        """
        self._ensure_not_degraded()

        if session_id not in self._session_locks:
            self._session_locks[session_id] = asyncio.Lock()

        async with self._session_locks[session_id]:
            # Update in-memory context
            if self._context_manager is not None:
                conv = self._context_manager.get_or_create_session(session_id)
                conv.add_message(Message(role="user", content=user_text))
                conv.add_message(Message(role="assistant", content=assistant_text))
                conv.apply_sliding_window()

            # Update conversation manager session state
            if self._conversation_manager is not None:
                session = self._conversation_manager.get_session(session_id)
                if session is not None:
                    session.touch()
                    session.message_count += 2

        await self._emit_event("runtime.session_updated", {
            "session_id": session_id,
            "user_text_length": len(user_text),
            "assistant_text_length": len(assistant_text),
        })

    async def mark_session_processing(self, session_id: str) -> None:
        """Mark a session as actively processing."""
        session = await self.get_or_create_session(session_id)
        if hasattr(session, "state"):
            session.state = "PROCESSING"

    async def mark_session_idle(self, session_id: str) -> None:
        """Mark a session as idle after processing."""
        session = await self.get_or_create_session(session_id)
        if hasattr(session, "state"):
            session.state = "IDLE"

    async def increment_session_errors(self, session_id: str) -> None:
        """Increment error count for a session."""
        if self._conversation_manager is not None:
            session = self._conversation_manager.get_session(session_id)
            if session is not None and hasattr(session, "error_count"):
                session.error_count += 1

    def get_session(self, session_id: str) -> object | None:
        """Retrieve a session without creating it."""
        if self._conversation_manager is None:
            return None
        return self._conversation_manager.get_session(session_id)

    def has_session(self, session_id: str) -> bool:
        """Check if a session exists."""
        if self._conversation_manager is None:
            return False
        return self._conversation_manager.has_session(session_id)

    @property
    def active_sessions(self) -> list[str]:
        """Get IDs of all active sessions."""
        if self._conversation_manager is None:
            return []
        return self._conversation_manager.active_sessions

    @property
    def session_count(self) -> int:
        """Get total number of tracked sessions."""
        if self._conversation_manager is None:
            return 0
        return self._conversation_manager.session_count

    # ------------------------------------------------------------------
    # Idle cleanup
    # ------------------------------------------------------------------

    def _start_cleanup_task(self) -> None:
        """Start the background idle-cleanup coroutine."""
        if self._cleanup_task is None or self._cleanup_task.done():
            import asyncio
            self._cleanup_task = asyncio.create_task(self._idle_cleanup_loop())
            self._logger.debug("Idle cleanup task started")

    def _stop_cleanup_task(self) -> None:
        """Cancel the background idle-cleanup coroutine."""
        if self._cleanup_task is not None and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            self._logger.debug("Idle cleanup task cancelled")
        self._cleanup_task = None

    async def _idle_cleanup_loop(self) -> None:
        """Background loop that sweeps expired sessions."""
        while True:
            try:
                import asyncio
                await asyncio.sleep(self._idle_cleanup_interval)
                if self._conversation_manager is not None:
                    router = getattr(self._conversation_manager, "router", None)
                    if router is not None:
                        timed_out = router.cleanup_expired()
                        for sid in timed_out:
                            self._logger.info("Session timed out via cleanup: %s", sid)
                            await self._emit_event("runtime.session_timeout", {
                                "session_id": sid,
                            })
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._logger.warning("Idle cleanup error: %s", exc)

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    async def _emit_event(self, event_type: str, data: dict[str, Any]) -> None:
        if self._event_bus is None:
            return
        emit = getattr(self._event_bus, "emit", None)
        if emit is not None:
            await emit(event_type, data)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_not_degraded(self) -> None:
        if self._degraded:
            from backend.exceptions import ModuleDegradedError
            raise ModuleDegradedError(
                "SessionManager is degraded",
                context={"module": "runtime.session_manager"},
            )

    # ------------------------------------------------------------------
    # Properties for testing/debugging
    # ------------------------------------------------------------------

    @property
    def conversation_manager(self) -> ConversationManager | None:
        return self._conversation_manager

    @property
    def context_manager(self) -> ContextManager | None:
        return self._context_manager


class _SimpleSession:
    """Fallback session object when ConversationManager is unavailable."""

    VALID_STATES = {"ACTIVE", "IDLE", "PROCESSING", "TIMEOUT", "CLOSED", "ERROR"}

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.state = "ACTIVE"
        self.last_activity = time.time()
        self.created_at = time.time()
        self.timeout_seconds = 300.0
        self.message_count = 0
        self.total_requests: int = 0
        self.total_errors: int = 0
        self.total_tokens: int = 0
        self.metadata: dict[str, Any] = {}

    def touch(self) -> None:
        self.last_activity = time.time()
        if self.state in ("IDLE", "ACTIVE"):
            self.state = "ACTIVE"

    @property
    def is_expired(self) -> bool:
        if self.state in ("TIMEOUT", "CLOSED"):
            return True
        return time.time() - self.last_activity > self.timeout_seconds

    @property
    def is_active(self) -> bool:
        return self.state not in ("TIMEOUT", "CLOSED")

    @property
    def state_duration(self) -> float:
        """Return seconds since last activity."""
        return time.time() - self.last_activity
