"""
ConversationPipeline — orchestrates the full request-to-response flow.

19_Request_Lifecycle.md — Full request lifecycle (Phases 1–6).
07_Module_Design.md §2 — Module responsibilities.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from backend.modules.conversation._bridge import ConversationMemoryBridge
from backend.modules.conversation._history import ConversationHistory
from backend.modules.conversation._session import ConversationSession
from backend.modules.conversation._state import ConversationState
from backend.types import LLMResponse, Message, TokenUsage, UserRequest, UserResponse

_LOG = logging.getLogger("naira.conversation")


class ConversationPipeline:
    """Orchestrates the full request processing lifecycle.

    Coordinates the flow:
    1. Compile system prompt (PromptManager).
    2. Build context with sliding window (ContextManager).
    3. Generate LLM response (LLMManager).
    4. Store messages to persistent memory (MemoryManager via bridge).
    5. Emit lifecycle events (EventBus).
    6. Produce ``UserResponse``.

    Parameters
    ----------
    context_manager : Any | None
        ``ContextManager`` instance injected at boot.
    prompt_manager : Any | None
        ``PromptManager`` instance injected at boot.
    llm_manager : Any | None
        ``LLMManager`` instance injected at boot.
    bridge : ConversationMemoryBridge | None
        Persistence bridge for storing/loading history.
    history : ConversationHistory | None
        History manager for context merging.
    event_bus : Any | None
        ``EventBus`` instance for event emission.
    logger : logging.Logger | None
        Module-scoped logger.
    """

    def __init__(
        self,
        context_manager: object | None = None,
        prompt_manager: object | None = None,
        llm_manager: object | None = None,
        bridge: ConversationMemoryBridge | None = None,
        history: ConversationHistory | None = None,
        event_bus: object | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._context_manager = context_manager
        self._prompt_manager = prompt_manager
        self._llm_manager = llm_manager
        self._bridge = bridge or ConversationMemoryBridge()
        self._history = history
        self._event_bus = event_bus
        self._logger = logger or _LOG
        self._degraded: bool = False

    @property
    def degraded(self) -> bool:
        return self._degraded

    def degrade(self) -> None:
        self._degraded = True

    async def process(
        self,
        request: UserRequest,
        session: ConversationSession,
    ) -> UserResponse:
        """Process a single user request through the full pipeline.

        Parameters
        ----------
        request : UserRequest
            The inbound user request.
        session : ConversationSession
            The resolved session for this request.

        Returns
        -------
        UserResponse
            The outbound response.
        """
        if self._degraded:
            return UserResponse(
                request_id=request.id,
                text="Conversation pipeline is degraded.",
                source=request.source,
                duration_ms=0.0,
            )

        session.state = ConversationState.PROCESSING
        start_time = time.time()

        try:
            await self._emit_event("conversation.request_start", {
                "session_id": request.session_id,
                "request_id": str(request.id),
            })

            system_prompt = self._compile_system_prompt()

            context = self._build_context(
                session_id=request.session_id,
                text=request.text,
                system_prompt=system_prompt,
            )

            response = await self._generate_response(
                prompt=system_prompt,
                context_messages=context.messages if hasattr(context, "messages") else [],
            )

            await self._store_conversation_turn(
                session_id=request.session_id,
                user_text=request.text,
                assistant_text=response.text,
            )

            self._update_in_memory_session(request.session_id, response.text)

            duration_ms = (time.time() - start_time) * 1000
            session.state = ConversationState.ACTIVE
            session.message_count += 2

            await self._emit_event("conversation.request_complete", {
                "session_id": request.session_id,
                "request_id": str(request.id),
                "duration_ms": duration_ms,
                "token_usage": {
                    "prompt_tokens": response.token_usage.prompt_tokens,
                    "completion_tokens": response.token_usage.completion_tokens,
                    "total_tokens": response.token_usage.total_tokens,
                },
            })

            return UserResponse(
                request_id=request.id,
                text=response.text,
                source=request.source,
                duration_ms=duration_ms,
            )

        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000
            session.state = ConversationState.ACTIVE
            self._logger.error("Pipeline error: %s", exc)

            await self._emit_event("conversation.request_error", {
                "session_id": request.session_id,
                "request_id": str(request.id),
                "error": str(exc),
            })

            return UserResponse(
                request_id=request.id,
                text="I encountered an error while processing your request.",
                source=request.source,
                duration_ms=duration_ms,
            )

    # ------------------------------------------------------------------
    # Pipeline stages
    # ------------------------------------------------------------------

    def _compile_system_prompt(self) -> str:
        """Phase 4: compile the system prompt via PromptManager."""
        if self._prompt_manager is None:
            return ""
        compile_fn = getattr(self._prompt_manager, "compile", None)
        if compile_fn is not None:
            return compile_fn()
        return ""

    def _build_context(
        self, session_id: str, text: str, system_prompt: str
    ) -> object:
        """Phase 3: build context via ContextManager."""
        if self._context_manager is None:
            return _empty_context()
        build = getattr(self._context_manager, "build_context", None)
        if build is not None:
            return build(session_id, text, system_prompt)
        return _empty_context()

    async def _generate_response(
        self,
        prompt: str,
        context_messages: list[Message],
    ) -> LLMResponse:
        """Phase 5: generate response via LLMManager."""
        if self._llm_manager is None:
            return _empty_llm_response()
        generate = getattr(self._llm_manager, "generate", None)
        if generate is not None:
            return await generate(prompt, context_messages)
        return _empty_llm_response()

    async def _store_conversation_turn(
        self,
        session_id: str,
        user_text: str,
        assistant_text: str,
    ) -> None:
        """Persist both sides of the conversation turn."""
        if self._bridge is None or not self._bridge.available:
            return
        try:
            await self._bridge.store_message(
                session_id, Message(role="user", content=user_text)
            )
            await self._bridge.store_message(
                session_id, Message(role="assistant", content=assistant_text)
            )
        except Exception as exc:
            self._logger.warning("Failed to persist messages: %s", exc)

    def _update_in_memory_session(
        self, session_id: str, assistant_text: str
    ) -> None:
        """Store the assistant response in the in-memory context session
        so subsequent turns include it.
        """
        if self._context_manager is None:
            return
        get_sess = getattr(self._context_manager, "get_session", None)
        if get_sess is not None:
            conv_ctx = get_sess(session_id)
            if conv_ctx is not None:
                add = getattr(conv_ctx, "add_assistant_message", None)
                if add is not None:
                    add(assistant_text)

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    async def _emit_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit an event via the EventBus (if available)."""
        if self._event_bus is None:
            return
        emit = getattr(self._event_bus, "emit", None)
        if emit is not None:
            await emit(event_type, data)


def _empty_context() -> object:
    """Return a minimal context-like object for fallback paths."""
    return type("EmptyContext", (), {"messages": [], "system_prompt": ""})()


def _empty_llm_response() -> LLMResponse:
    """Return a minimal LLMResponse for fallback paths when no LLM is available."""
    return LLMResponse(
        text="",
        tool_calls=None,
        finish_reason="error",
        token_usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        provider="none",
        duration_ms=0.0,
    )
