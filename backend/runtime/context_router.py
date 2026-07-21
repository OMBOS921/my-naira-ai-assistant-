"""
ContextRouter — routes context assembly to ContextManager.

Handles session-aware context building with sliding window and
token budget management.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.modules.context import ContextManager
from backend.orchestrator import EventBus
from backend.types import Context, Message

_LOG = logging.getLogger("naira.runtime.context_router")


class ContextRouter:
    """Routes context assembly requests to the ContextManager.

    Maintains session-to-context mapping and delegates to
    ContextManager for actual context building.

    Parameters
    ----------
    context_manager : ContextManager | None
        ContextManager instance.
    event_bus : EventBus | None
        EventBus for event emission.
    logger : logging.Logger | None
        Module-scoped logger.
    """

    def __init__(
        self,
        *,
        context_manager: ContextManager | None = None,
        event_bus: EventBus | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._context_manager = context_manager
        self._event_bus = event_bus
        self._logger = logger or _LOG
        self._degraded: bool = False
        self._initialized: bool = False

    # ------------------------------------------------------------------
    # Module lifecycle
    # ------------------------------------------------------------------

    async def async_init(self) -> None:
        """Initialise the context router."""
        if self._context_manager is not None:
            init = getattr(self._context_manager, "async_init", None)
            if init is not None:
                await init()
        self._initialized = True
        self._logger.debug("Context router initialised")

    async def async_shutdown(self) -> None:
        """Release resources."""
        if self._context_manager is not None:
            shutdown = getattr(self._context_manager, "async_shutdown", None)
            if shutdown is not None:
                await shutdown()
        self._degraded = False
        self._initialized = False
        self._logger.debug("Context router shut down")

    def degrade(self) -> None:
        """Mark as degraded."""
        self._degraded = True
        if self._context_manager is not None:
            degrade = getattr(self._context_manager, "degrade", None)
            if degrade is not None:
                degrade()
        self._logger.warning("Context router marked degraded")

    @property
    def degraded(self) -> bool:
        return self._degraded

    @property
    def initialized(self) -> bool:
        return self._initialized

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_context(
        self,
        session_id: str,
        user_text: str,
        system_prompt: str,
    ) -> Context:
        """Build a context for LLM inference.

        Parameters
        ----------
        session_id : str
            Session identifier.
        user_text : str
            Current user message.
        system_prompt : str
            Compiled system prompt.

        Returns
        -------
        Context
            Immutable context payload with messages and token count.
        """
        self._ensure_not_degraded()

        if self._context_manager is None:
            self._logger.warning("No ContextManager available — returning empty context")
            return _empty_context()

        try:
            return self._context_manager.build_context(
                session_id=session_id,
                text=user_text,
                system_prompt=system_prompt,
            )
        except Exception as exc:
            self._logger.error("Context build failed: %s", exc)
            return _empty_context()

    def get_session_context(self, session_id: str) -> list[Message] | None:
        """Get the raw message history for a session.

        Parameters
        ----------
        session_id : str
            Session identifier.

        Returns
        -------
        list[Message] | None
            Message history if session exists, else None.
        """
        if self._context_manager is None:
            return None
        session = self._context_manager.get_session(session_id)
        if session is None:
            return None
        return session.messages

    def reset_session_context(self, session_id: str) -> None:
        """Clear all messages for a session."""
        if self._context_manager is None:
            return
        self._context_manager.reset_session(session_id)
        self._logger.debug("Reset context for session: %s", session_id)

    def remove_session_context(self, session_id: str) -> None:
        """Remove a session's context entirely."""
        if self._context_manager is None:
            return
        self._context_manager.remove_session(session_id)
        self._logger.debug("Removed context for session: %s", session_id)

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
                "ContextRouter is degraded",
                context={"module": "runtime.context_router"},
            )

    # ------------------------------------------------------------------
    # Properties for testing/debugging
    # ------------------------------------------------------------------

    @property
    def context_manager(self) -> ContextManager | None:
        return self._context_manager

    @property
    def active_sessions(self) -> list[str]:
        if self._context_manager is None:
            return []
        return self._context_manager.active_sessions

    @property
    def session_count(self) -> int:
        if self._context_manager is None:
            return 0
        return self._context_manager.session_count


def _empty_context() -> Context:
    """Return a minimal Context for fallback paths."""
    return Context(
        system_prompt="",
        messages=[],
        token_count=0,
    )
