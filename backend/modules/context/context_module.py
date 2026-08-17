from typing import Any
"""
ContextManager — the single public class for the context module.

07_Module_Design.md §2.D — Any Manager responsibilities.
19_Request_Lifecycle.md §3 — Phase 3: Any Assembly.
21_System_Contracts.md §4.2 — ModuleInterface protocol.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging

from backend.exceptions import ModuleDegradedError
from backend.modules.context._builder import ContextBuilder
from backend.modules.context._conversation import ConversationContext
from backend.types import Message
_LOG = logging.getLogger("naira.context")


class ContextManager:
    """Central context manager — session-aware, in-memory.

    Owns a collection of ``ConversationContext`` instances keyed by
    ``session_id``.  Builds immutable ``Any`` payloads for the
    LLM pipeline via ``build_context()``.

    Conforms to ``ModuleInterface`` (``backend/types.py``).

    Parameters
    ----------
    config : Any | None
        Application configuration (``AppConfig`` or compatible).
    logger : logging.Logger | None
        Module-scoped logger.  If ``None``, a default logger is used.
    max_tokens : int
        Default token budget for sliding-window truncation.
    memory_port : MemoryPort | None
        Optional ``MemoryPort`` adapter injected at boot for
        long-term persistence (20_Dependency_Rules.md §2).
    """

    def __init__(
        self,
        *,
        config: object | None = None,
        logger: logging.Logger | None = None,
        max_tokens: int = 4096,
        memory_port: object | None = None,
        memory_manager: object | None = None,
        event_bus: object | None = None,
    ) -> None:
        self._config = config
        self._logger = logger or _LOG
        self._max_tokens = max_tokens
        self._memory_port = memory_port
        self._memory_manager = memory_manager
        self._event_bus = event_bus
        self._sessions: dict[str, ConversationContext] = {}
        self._degraded: bool = False

    # ------------------------------------------------------------------
    # Module lifecycle  (ModuleInterface protocol)
    # ------------------------------------------------------------------

    async def async_init(self) -> None:
        """Initialise the context manager.

        No heavyweight setup required for in-memory operation.
        """
        self._logger.info(
            "Any manager initialised — max_tokens=%d", self._max_tokens
        )

    async def async_shutdown(self) -> None:
        """Release all session state."""
        self._sessions.clear()
        self._degraded = False
        self._logger.info("Any manager shut down.")

    def degrade(self) -> None:
        """Release resources and mark as degraded."""
        self._sessions.clear()
        self._degraded = True
        self._logger.warning("Any manager marked degraded")

    @property
    def degraded(self) -> bool:
        return self._degraded

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_memory_manager(self, memory_manager: object) -> None:
        """Attach memory manager post-construction if needed."""
        self._memory_manager = memory_manager

    def build_context(
        self, session_id: str, text: str, system_prompt: str = ""
    ) -> Any:
        """Build a ``Any`` for LLM inference.

        19_Request_Lifecycle.md §3 (Phase 3: Any Assembly).

        1. Retrieves or creates a ``ConversationContext`` for the session.
        2. Appends the current user message.
        3. Applies the sliding window if the token budget is exceeded.
        4. Queries memory engines for dynamic profile & timeline event context.
        5. Queries MemoryManager asynchronously for relevant memories (500ms timeout).
        6. Returns an immutable ``Any`` dataclass.
        """
        self._ensure_not_degraded()

        conv = self._get_or_create_session(session_id)

        user_msg = Message(role="user", content=text)
        conv.add_message(user_msg)

        conv.apply_sliding_window()

        dynamic_context = self._get_dynamic_memory_context(session_id)
        relevant_memories = self._query_relevant_memories_sync(text, timeout=0.5)

        return ContextBuilder.build(
            system_prompt=system_prompt,
            messages=conv.messages,
            max_tokens=self._max_tokens,
            dynamic_context=dynamic_context,
            relevant_memories=relevant_memories,
        )

    async def build_context_async(
        self,
        session_id: str,
        text: str,
        system_prompt: str = "",
        memory_timeout: float = 0.5,
    ) -> Any:
        """Build a ``Any`` asynchronously with auto-context memory retrieval (500ms timeout)."""
        self._ensure_not_degraded()

        conv = self._get_or_create_session(session_id)

        user_msg = Message(role="user", content=text)
        conv.add_message(user_msg)

        conv.apply_sliding_window()

        dynamic_context = self._get_dynamic_memory_context(session_id)
        relevant_memories = await self._query_relevant_memories_async(text, timeout=memory_timeout)

        return ContextBuilder.build(
            system_prompt=system_prompt,
            messages=conv.messages,
            max_tokens=self._max_tokens,
            dynamic_context=dynamic_context,
            relevant_memories=relevant_memories,
        )

    async def _query_relevant_memories_async(
        self, text: str, timeout: float = 0.5
    ) -> str:
        """Query MemoryManager for relevant memories matching text within strict timeout."""
        if self._memory_manager is None or not text or not text.strip():
            return ""

        handler = getattr(self._memory_manager, "search_memory_tool_handler", None)
        if not callable(handler):
            return ""

        try:
            res = await asyncio.wait_for(
                handler(query=text, search_type="all", limit=3),
                timeout=timeout,
            )
            if getattr(res, "status", None) == "success" and getattr(res, "output", None):
                out_str = str(res.output).strip()
                if out_str and "No memory found" not in out_str:
                    return out_str
        except Exception as exc:
            self._logger.debug("Relevant memory retrieval timeout or failure: %s", exc)

        return ""

    def _query_relevant_memories_sync(self, text: str, timeout: float = 0.5) -> str:
        """Synchronous wrapper for relevant memory query with strict timeout."""
        if self._memory_manager is None or not text or not text.strip():
            return ""
        try:
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        fut = pool.submit(
                            asyncio.run, self._query_relevant_memories_async(text, timeout=timeout)
                        )
                        return fut.result(timeout=timeout + 0.1)
            except RuntimeError:
                return asyncio.run(self._query_relevant_memories_async(text, timeout=timeout))
        except Exception as exc:
            self._logger.debug("Sync relevant memory query failed: %s", exc)

        return ""

    def _get_dynamic_memory_context(self, session_id: str) -> str:
        """Fetch user profile and top 3 recent session milestone events."""
        parts: list[str] = []
        try:
            if self._memory_manager is not None:
                user_prof = getattr(self._memory_manager, "user_profile", None)
                timeline = getattr(self._memory_manager, "timeline_engine", None)
                if user_prof and hasattr(user_prof, "get_summary_for_prompt"):
                    up_str = user_prof.get_summary_for_prompt()
                    if up_str:
                        parts.append(up_str)
                if timeline and hasattr(timeline, "get_summary_for_prompt"):
                    tl_str = timeline.get_summary_for_prompt(limit=3)
                    if tl_str:
                        parts.append(tl_str)
            elif self._memory_port is not None:
                u_prof = getattr(self._memory_port, "_user_profile_engine", None)
                t_engine = getattr(self._memory_port, "_timeline_engine", None)
                if u_prof and hasattr(u_prof, "get_summary_for_prompt"):
                    up_str = u_prof.get_summary_for_prompt()
                    if up_str:
                        parts.append(up_str)
                if t_engine and hasattr(t_engine, "get_summary_for_prompt"):
                    tl_str = t_engine.get_summary_for_prompt(limit=3)
                    if tl_str:
                        parts.append(tl_str)
        except Exception as exc:
            self._logger.debug("Failed to retrieve dynamic memory context: %s", exc)

        return "\n\n".join(parts)

    def add_assistant_message(self, session_id: str, content: str) -> None:
        """Add an assistant response message to session context history."""
        conv = self._get_or_create_session(session_id)
        conv.add_message(Message(role="assistant", content=content))

    def get_session(self, session_id: str) -> ConversationContext | None:
        """Retrieve a session's ``ConversationContext``.

        Returns ``None`` if the session does not exist.
        """
        return self._sessions.get(session_id)

    def get_or_create_session(self, session_id: str) -> ConversationContext:
        """Get an existing session or create a new one."""
        return self._get_or_create_session(session_id)

    def reset_session(self, session_id: str) -> None:
        """Clear all messages for a session.

        The session remains active with an empty history.
        """
        conv = self._sessions.get(session_id)
        if conv is not None:
            conv.clear()
            self._logger.info("Session reset: %s", session_id)

    def remove_session(self, session_id: str) -> None:
        """Remove a session entirely."""
        self._sessions.pop(session_id, None)
        self._logger.info("Session removed: %s", session_id)

    @property
    def active_sessions(self) -> list[str]:
        """Return a list of active session IDs."""
        return list(self._sessions.keys())

    @property
    def session_count(self) -> int:
        """Return the number of active sessions."""
        return len(self._sessions)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_create_session(self, session_id: str) -> ConversationContext:
        conv = self._sessions.get(session_id)
        if conv is None:
            conv = ConversationContext(
                session_id=session_id,
                max_tokens=self._max_tokens,
            )
            self._sessions[session_id] = conv
            self._logger.debug("Created new session: %s", session_id)
        return conv

    def _ensure_not_degraded(self) -> None:
        if self._degraded:
            raise ModuleDegradedError(
                "ContextManager is degraded",
                context={"module": "context"},
            )
