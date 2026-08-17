from typing import Any
"""
ConversationManager — the single public class for the conversation module.

07_Module_Design.md §2 — Module responsibilities.
19_Request_Lifecycle.md — Full request lifecycle.
21_System_Contracts.md §4.2 — ModuleInterface protocol.
"""

from __future__ import annotations

import asyncio
import logging

from backend.exceptions import ModuleDegradedError
from backend.modules.conversation._bridge import ConversationMemoryBridge
from backend.modules.conversation._history import ConversationHistory
from backend.modules.conversation._pipeline import ConversationPipeline
from backend.modules.conversation._router import ConversationRouter
from backend.modules.conversation._session import ConversationSession
from backend.types import UserRequest, UserResponse
_LOG = logging.getLogger("naira.conversation")


class ConversationManager:
    """Central conversation runtime brain.

    Receives ``UserRequest`` and produces ``UserResponse`` by
    orchestrating the full pipeline through:
    - ``ConversationRouter`` — multi-session resolution
    - ``ConversationPipeline`` — request processing flow
    - ``ConversationMemoryBridge`` — persistent storage
    - ``ConversationHistory`` — context merging

    Conforms to ``ModuleInterface`` (``backend/types.py``).

    Parameters
    ----------
    config : Any | None
        Application configuration (``AppConfig`` or compatible).
    logger : logging.Logger | None
        Module-scoped logger.  If ``None``, a default logger is used.
    context_manager : Any | None
        ``ContextManager`` instance for context assembly.
    prompt_manager : Any | None
        ``PromptManager`` instance for prompt compilation.
    llm_manager : Any | None
        ``LLMManager`` instance for response generation.
    memory_manager : Any | None
        ``MemoryManager`` instance for persistent storage.
    event_bus : Any | None
        ``EventBus`` instance for event emission.
    session_timeout : float
        Default idle timeout in seconds (default 300).
    idle_cleanup_interval : float
        Interval for the idle cleanup task in seconds (default 60).
    max_tokens : int
        Default token budget for sliding-window truncation (default 4096).
    """

    def __init__(
        self,
        *,
        config: object | None = None,
        logger: logging.Logger | None = None,
        context_manager: object | None = None,
        prompt_manager: object | None = None,
        llm_manager: object | None = None,
        memory_manager: object | None = None,
        event_bus: object | None = None,
        session_timeout: float = 300.0,
        idle_cleanup_interval: float = 60.0,
        max_tokens: int = 4096,
    ) -> None:
        self._config = config
        self._logger = logger or _LOG
        self._event_bus = event_bus
        self._degraded: bool = False
        self._initialized: bool = False
        self._cleanup_task: asyncio.Task[None] | None = None

        self._session_timeout = session_timeout
        self._idle_cleanup_interval = idle_cleanup_interval
        self._max_tokens = max_tokens

        self._router = ConversationRouter(
            session_timeout=session_timeout,
            logger=logger,
        )

        self._bridge = ConversationMemoryBridge(
            memory_manager=memory_manager,
            logger=logger,
        )

        self._history = ConversationHistory(
            bridge=self._bridge,
            logger=logger,
            max_tokens=max_tokens,
        )

        self._pipeline = ConversationPipeline(
            context_manager=context_manager,
            prompt_manager=prompt_manager,
            llm_manager=llm_manager,
            bridge=self._bridge,
            history=self._history,
            event_bus=event_bus,
            logger=logger,
        )

    # ------------------------------------------------------------------
    # Module lifecycle  (ModuleInterface protocol)
    # ------------------------------------------------------------------

    async def async_init(self) -> None:
        """Initialise the conversation manager.

        Starts the background idle-cleanup task.
        """
        self._logger.info(
            "Conversation manager initialising — timeout=%ds cleanup=%ds max_tokens=%d",
            self._session_timeout,
            self._idle_cleanup_interval,
            self._max_tokens,
        )
        self._initialized = True
        self._start_cleanup_task()
        self._logger.info("Conversation manager initialised")

    async def async_shutdown(self) -> None:
        """Release all resources and stop the cleanup task."""
        self._stop_cleanup_task()
        self._router = ConversationRouter(
            session_timeout=self._session_timeout,
        )
        self._degraded = False
        self._initialized = False
        self._logger.info("Conversation manager shut down.")

    def degrade(self) -> None:
        """Mark the module as degraded and stop the cleanup task."""
        self._stop_cleanup_task()
        if hasattr(self, "_pipeline") and self._pipeline is not None:
            self._pipeline.degrade()
        self._degraded = True
        self._logger.warning("Conversation manager marked degraded")

    @property
    def degraded(self) -> bool:
        return self._degraded

    @property
    def initialized(self) -> bool:
        return self._initialized

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def process_request(self, request: UserRequest) -> UserResponse:
        """Process a single user request and return a response.

        19_Request_Lifecycle.md — Phases 1–6.

        Parameters
        ----------
        request : UserRequest
            The immutable inbound request.

        Returns
        -------
        UserResponse
            The outbound response.

        Raises
        ------
        ModuleDegradedError
            If the manager is in a degraded state.
        """
        self._ensure_not_degraded()

        session = self._router.route(request.session_id)

        response = await self._pipeline.process(request, session)

        return response

    def get_session(self, session_id: str) -> ConversationSession | None:
        """Retrieve a session from the router.

        Returns ``None`` if the session does not exist.
        """
        return self._router.get_session(session_id)

    def has_session(self, session_id: str) -> bool:
        """Return ``True`` if a session with the given ID exists."""
        return self._router.has_session(session_id)

    async def close_session(self, session_id: str) -> None:
        """Close a session and stop accepting new requests for it."""
        self._ensure_not_degraded()
        await self._router.close_session(session_id)

    def remove_session(self, session_id: str) -> None:
        """Remove a session entirely from the registry."""
        self._router.remove_session(session_id)

    @property
    def active_sessions(self) -> list[str]:
        """Return IDs of all active (non-closed) sessions."""
        return self._router.active_sessions

    @property
    def session_count(self) -> int:
        """Return the total number of tracked sessions."""
        return self._router.session_count

    @property
    def router(self) -> ConversationRouter:
        """Expose the router for inspection (testing/debugging)."""
        return self._router

    @property
    def pipeline(self) -> ConversationPipeline:
        """Expose the pipeline for inspection (testing/debugging)."""
        return self._pipeline

    @property
    def bridge(self) -> ConversationMemoryBridge:
        """Expose the memory bridge for inspection (testing/debugging)."""
        return self._bridge

    # ------------------------------------------------------------------
    # Idle cleanup
    # ------------------------------------------------------------------

    def _start_cleanup_task(self) -> None:
        """Start the background idle-cleanup coroutine."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._idle_cleanup_loop())
            self._logger.debug("Idle cleanup task started")

    def _stop_cleanup_task(self) -> None:
        """Cancel the background idle-cleanup coroutine."""
        if self._cleanup_task is not None and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            self._logger.debug("Idle cleanup task cancelled")
        self._cleanup_task = None

    async def _idle_cleanup_loop(self) -> None:
        """Background loop that sweeps expired sessions.

        Runs every ``_idle_cleanup_interval`` seconds.  Marks
        expired sessions as TIMEOUT and emits events for each.
        """
        while True:
            try:
                await asyncio.sleep(self._idle_cleanup_interval)
                timed_out = self._router.cleanup_expired()
                for sid in timed_out:
                    self._logger.info("Session timed out via cleanup: %s", sid)
                    if self._event_bus is not None:
                        emit = getattr(self._event_bus, "emit", None)
                        if emit is not None:
                            await emit("conversation.session_timeout", {
                                "session_id": sid,
                            })
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._logger.warning("Idle cleanup error: %s", exc)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_not_degraded(self) -> None:
        if self._degraded:
            raise ModuleDegradedError(
                "ConversationManager is degraded",
                context={"module": "conversation"},
            )
