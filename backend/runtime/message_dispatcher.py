"""
MessageDispatcher — dispatches messages to the runtime pipeline.

Handles incoming user messages, routes them through the complete
execution pipeline, and returns final responses.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from backend.orchestrator import EventBus
from backend.runtime.context_router import ContextRouter
from backend.runtime.request_pipeline import RequestPipeline
from backend.runtime.response_pipeline import ResponsePipeline
from backend.runtime.session_manager import SessionManager
from backend.types import UserRequest, UserResponse
_LOG = logging.getLogger("naira.runtime.message_dispatcher")


class MessageDispatcher:
    """Dispatches user messages through the complete AI pipeline.

    Coordinates:
    1. RequestPipeline — context assembly, prompt compilation
    2. ResponsePipeline — LLM generation, tool calling, streaming
    3. SessionManager — session state persistence
    4. EventBus — stage event emission

    Parameters
    ----------
    request_pipeline : RequestPipeline | None
        RequestPipeline instance.
    response_pipeline : ResponsePipeline | None
        ResponsePipeline instance.
    session_manager : SessionManager | None
        SessionManager instance.
    context_router : ContextRouter | None
        ContextRouter instance.
    event_bus : EventBus | None
        EventBus for event emission.
    logger : logging.Logger | None
        Module-scoped logger.
    """

    def __init__(
        self,
        *,
        request_pipeline: RequestPipeline | None = None,
        response_pipeline: ResponsePipeline | None = None,
        session_manager: SessionManager | None = None,
        context_router: ContextRouter | None = None,
        event_bus: EventBus | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._request_pipeline = request_pipeline
        self._response_pipeline = response_pipeline
        self._session_manager = session_manager
        self._context_router = context_router
        self._event_bus = event_bus
        self._logger = logger or _LOG
        self._degraded: bool = False
        self._initialized: bool = False

    # ------------------------------------------------------------------
    # Module lifecycle
    # ------------------------------------------------------------------

    async def async_init(self) -> None:
        """Initialise the message dispatcher."""
        components = [
            self._request_pipeline,
            self._response_pipeline,
            self._session_manager,
            self._context_router,
        ]
        for comp in components:
            if comp is not None:
                init = getattr(comp, "async_init", None)
                if init is not None:
                    await init()

        self._initialized = True
        self._logger.debug("Message dispatcher initialised")

    async def async_shutdown(self) -> None:
        """Release resources."""
        components = [
            self._context_router,
            self._session_manager,
            self._response_pipeline,
            self._request_pipeline,
        ]
        for comp in components:
            if comp is not None:
                shutdown = getattr(comp, "async_shutdown", None)
                if shutdown is not None:
                    await shutdown()

        self._degraded = False
        self._initialized = False
        self._logger.debug("Message dispatcher shut down")

    def degrade(self) -> None:
        """Mark as degraded."""
        self._degraded = True
        components = [
            self._request_pipeline,
            self._response_pipeline,
            self._session_manager,
            self._context_router,
        ]
        for comp in components:
            if comp is not None:
                degrade = getattr(comp, "degrade", None)
                if degrade is not None:
                    degrade()
        self._logger.warning("Message dispatcher marked degraded")

    @property
    def degraded(self) -> bool:
        return self._degraded

    @property
    def initialized(self) -> bool:
        return self._initialized

    # ------------------------------------------------------------------
    # Public API — Non-streaming
    # ------------------------------------------------------------------

    async def dispatch(self, request: UserRequest) -> UserResponse:
        """Dispatch a user request through the full pipeline.

        Parameters
        ----------
        request : UserRequest
            Immutable inbound request.

        Returns
        -------
        UserResponse
            Outbound response.
        """
        self._ensure_not_degraded()

        session_id = request.session_id
        request_id = request.id

        await self._emit_event("runtime.dispatch_start", {
            "session_id": session_id,
            "request_id": str(request_id),
            "source": request.source,
        })

        try:
            # 1. Resolve/create session
            session = await self._session_manager.get_or_create_session(session_id)
            session.touch()

            await self._emit_event("runtime.session_resolved", {
                "session_id": session_id,
                "request_id": str(request_id),
                "is_new": session.message_count == 0,
            })

            # 2. Build context and compile prompt via RequestPipeline
            if self._request_pipeline is not None:
                pipeline_result = await self._request_pipeline.process(request)
            else:
                pipeline_result = None

            # 3. Extract compiled prompt and context
            if pipeline_result is not None:
                system_prompt = pipeline_result.system_prompt
                context_messages = pipeline_result.messages
                tool_defs = pipeline_result.tool_defs
            else:
                system_prompt = ""
                context_messages = []
                tool_defs = []

            await self._emit_event("runtime.prompt_compiled", {
                "session_id": session_id,
                "request_id": str(request_id),
                "system_prompt_length": len(system_prompt),
                "context_messages": len(context_messages),
                "tool_count": len(tool_defs),
            })

            # 4. Generate response via ResponsePipeline
            if self._response_pipeline is not None:
                llm_response = await self._response_pipeline.generate(
                    system_prompt=system_prompt,
                    messages=context_messages,
                    tool_defs=tool_defs,
                    session_id=session_id,
                )
            else:
                llm_response = _empty_llm_response()

            await self._emit_event("runtime.llm_response_received", {
                "session_id": session_id,
                "request_id": str(request_id),
                "provider": llm_response.provider,
                "finish_reason": llm_response.finish_reason,
                "token_usage": llm_response.token_usage.total_tokens,
                "text_length": len(llm_response.text),
            })

            # 5. Update session with conversation turn
            await self._session_manager.update_session(
                session_id=session_id,
                user_text=request.text,
                assistant_text=llm_response.text,
            )

            await self._emit_event("runtime.dispatch_complete", {
                "session_id": session_id,
                "request_id": str(request_id),
                "response_length": len(llm_response.text),
                "duration_ms": llm_response.duration_ms,
            })

            return UserResponse(
                request_id=request_id,
                text=llm_response.text,
                source=request.source,
                duration_ms=llm_response.duration_ms,
            )

        except Exception as exc:
            self._logger.error("Dispatch error: %s", exc)
            await self._emit_event("runtime.dispatch_error", {
                "session_id": session_id,
                "request_id": str(request_id),
                "error": str(exc),
            })
            return UserResponse(
                request_id=request_id,
                text="An error occurred while processing your request.",
                source=request.source,
                duration_ms=0.0,
            )

    # ------------------------------------------------------------------
    # Public API — Streaming
    # ------------------------------------------------------------------

    async def dispatch_stream(
        self,
        request: UserRequest,
    ) -> AsyncIterator[str]:
        """Dispatch a request and stream the response tokens.

        Parameters
        ----------
        request : UserRequest
            Immutable inbound request.

        Yields
        ------
        str
            Successive text chunks from the LLM.
        """
        self._ensure_not_degraded()

        session_id = request.session_id
        request_id = request.id

        await self._emit_event("runtime.dispatch_stream_start", {
            "session_id": session_id,
            "request_id": str(request_id),
            "source": request.source,
        })

        try:
            # 1. Resolve/create session
            session = await self._session_manager.get_or_create_session(session_id)
            session.touch()

            # 2. Build context and compile prompt
            if self._request_pipeline is not None:
                pipeline_result = await self._request_pipeline.process(request)
            else:
                pipeline_result = None

            if pipeline_result is not None:
                system_prompt = pipeline_result.system_prompt
                context_messages = pipeline_result.messages
                tool_defs = pipeline_result.tool_defs
            else:
                system_prompt = ""
                context_messages = []
                tool_defs = []

            await self._emit_event("runtime.stream_prompt_compiled", {
                "session_id": session_id,
                "request_id": str(request_id),
            })

            # 3. Stream response
            accumulated_text = ""

            if self._response_pipeline is not None:
                async for chunk in self._response_pipeline.generate_stream(
                    system_prompt=system_prompt,
                    messages=context_messages,
                    tool_defs=tool_defs,
                    session_id=session_id,
                ):
                    accumulated_text += chunk
                    yield chunk
            else:
                yield ""

            # 4. Update session
            await self._session_manager.update_session(
                session_id=session_id,
                user_text=request.text,
                assistant_text=accumulated_text,
            )

            await self._emit_event("runtime.dispatch_stream_complete", {
                "session_id": session_id,
                "request_id": str(request_id),
                "response_length": len(accumulated_text),
            })

        except Exception as exc:
            self._logger.error("Dispatch stream error: %s", exc)
            await self._emit_event("runtime.dispatch_stream_error", {
                "session_id": session_id,
                "request_id": str(request_id),
                "error": str(exc),
            })
            yield f"\n[Error: {exc}]"

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
                "MessageDispatcher is degraded",
                context={"module": "runtime.message_dispatcher"},
            )

    # ------------------------------------------------------------------
    # Properties for testing/debugging
    # ------------------------------------------------------------------

    @property
    def request_pipeline(self) -> RequestPipeline | None:
        return self._request_pipeline

    @property
    def response_pipeline(self) -> ResponsePipeline | None:
        return self._response_pipeline

    @property
    def session_manager(self) -> SessionManager | None:
        return self._session_manager

    @property
    def context_router(self) -> ContextRouter | None:
        return self._context_router


def _empty_llm_response() -> object:
    """Return a minimal Any for fallback paths."""
    from backend.types import Any
    return Any(
        text="", tool_calls=None, finish_reason="error", token_usage=Any(prompt_tokens=0, completion_tokens=0, total_tokens=0), provider="none", duration_ms=0.0, )