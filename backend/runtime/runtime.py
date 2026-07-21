"""
Runtime — main orchestrator for the end-to-end AI execution pipeline.

Wires together the request/response pipelines, tool router, context router,
session manager, and message dispatcher to form a complete execution flow.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from backend.exceptions import ModuleDegradedError
from backend.modules.context import ContextManager
from backend.modules.llm import LLMManager
from backend.modules.memory import MemoryManager
from backend.modules.prompt import PromptManager
from backend.modules.tools import ToolManager
from backend.orchestrator import EventBus
from backend.runtime.context_router import ContextRouter
from backend.runtime.fast_command_router import FastCommandRouter
from backend.runtime.message_dispatcher import MessageDispatcher
from backend.runtime.request_pipeline import RequestPipeline
from backend.runtime.response_pipeline import ResponsePipeline
from backend.runtime.session_manager import SessionManager
from backend.runtime.tool_router import ToolRouter
from backend.types import (
    LLMResponse,
    Message,
    TokenUsage,
    UserRequest,
    UserResponse,
)

_LOG = logging.getLogger("naira.runtime")


class Runtime:
    """End-to-end AI execution pipeline orchestrator.

    Accepts user messages, routes through the complete pipeline:
    1. FastCommandRouter — direct OS execution for deterministic commands
    2. RequestPipeline — builds RequestContext, resolves session, assembles context, compiles prompt
    3. LLM generation (via LLMManager) with optional tool calling (via ToolRouter)
    4. ResponsePipeline — processes LLM response, executes tools, streams output
    5. MemoryManager — stores conversation turn
    6. SessionManager — preserves conversation state
    7. EventBus — emits events at every stage

    Parameters
    ----------
    config : object | None
        Application configuration.
    logger : logging.Logger | None
        Module-scoped logger.
    context_manager : ContextManager | None
        ContextManager instance.
    prompt_manager : PromptManager | None
        PromptManager instance.
    llm_manager : LLMManager | None
        LLMManager instance.
    tool_manager : ToolManager | None
        ToolManager instance.
    memory_manager : MemoryManager | None
        MemoryManager instance.
    pc_control_manager : object | None
        PCControlManager instance.
    event_bus : EventBus | None
        EventBus instance.
    max_tool_iterations : int
        Maximum tool-calling iterations (default 10).
    """

    def __init__(
        self,
        *,
        config: object | None = None,
        logger: logging.Logger | None = None,
        context_manager: ContextManager | None = None,
        prompt_manager: PromptManager | None = None,
        llm_manager: LLMManager | None = None,
        tool_manager: ToolManager | None = None,
        memory_manager: MemoryManager | None = None,
        pc_control_manager: object | None = None,
        event_bus: EventBus | None = None,
        max_tool_iterations: int = 10,
    ) -> None:
        self._config = config
        self._logger = logger or _LOG
        self._event_bus = event_bus
        self._max_tool_iterations = max_tool_iterations
        self._degraded: bool = False
        self._initialized: bool = False

        # Core managers
        self._context_manager = context_manager
        self._prompt_manager = prompt_manager
        self._llm_manager = llm_manager
        self._tool_manager = tool_manager
        self._memory_manager = memory_manager
        self._pc_control_manager = pc_control_manager

        self._fast_command_router = FastCommandRouter(
            pc_control_manager=pc_control_manager,
            logger=logger,
        )

        # Pipeline components
        self._tool_router = ToolRouter(
            tool_manager=tool_manager,
            logger=logger,
        )
        self._request_pipeline = RequestPipeline(
            context_manager=context_manager,
            prompt_manager=prompt_manager,
            session_manager=None,  # Set after SessionManager creation
            tool_router=self._tool_router,
            event_bus=event_bus,
            logger=logger,
        )
        self._response_pipeline = ResponsePipeline(
            llm_manager=llm_manager,
            tool_router=self._tool_router,
            event_bus=event_bus,
            logger=logger,
            max_tool_iterations=max_tool_iterations,
            conversation_manager=None,
            context_manager=context_manager,
        )
        self._session_manager = SessionManager(
            conversation_manager=None,  # Will be set after init
            context_manager=context_manager,
            event_bus=event_bus,
            logger=logger,
        )
        self._message_dispatcher = MessageDispatcher(
            event_bus=event_bus,
            logger=logger,
        )

        # Wire session manager into request pipeline
        self._request_pipeline._session_manager = self._session_manager

    # ------------------------------------------------------------------
    # Module lifecycle (ModuleInterface protocol)
    # ------------------------------------------------------------------

    async def async_init(self) -> None:
        """Initialise all pipeline components."""
        await self._request_pipeline.async_init()
        await self._response_pipeline.async_init()
        await self._session_manager.async_init()
        await self._message_dispatcher.async_init()
        self._initialized = True
        self._logger.info("Runtime initialised")

    async def async_shutdown(self) -> None:
        """Release all resources."""
        await self._message_dispatcher.async_shutdown()
        await self._session_manager.async_shutdown()
        await self._response_pipeline.async_shutdown()
        await self._request_pipeline.async_shutdown()
        self._degraded = False
        self._initialized = False
        self._logger.info("Runtime shut down.")

    def degrade(self) -> None:
        """Mark the runtime as degraded."""
        self._degraded = True
        self._request_pipeline.degrade()
        self._response_pipeline.degrade()
        self._session_manager.degrade()
        self._message_dispatcher.degrade()
        self._logger.warning("Runtime marked degraded")

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
        """Process a single user request end-to-end (non-streaming).

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
            If the runtime is in a degraded state.
        """
        self._ensure_not_degraded()

        request_id = request.id
        session_id = request.session_id
        start_time = self._get_time()

        await self._emit_event("runtime.request_start", {
            "session_id": session_id,
            "request_id": str(request_id),
            "source": request.source,
        })

        try:
            # Stage 0: Fast Command Engine bypass check
            if self._fast_command_router and self._fast_command_router.is_fast_command(request.text):
                self._logger.info("Fast Command Router match: '%s' — executing directly", request.text)
                fast_result = await self._fast_command_router.execute_fast_command(request.text)
                duration_ms = (self._get_time() - start_time) * 1000

                await self._store_turn(session_id, request.text, fast_result)
                await self._session_manager.update_session(
                    session_id=session_id,
                    user_text=request.text,
                    assistant_text=fast_result,
                )
                await self._emit_event("runtime.request_complete", {
                    "session_id": session_id,
                    "request_id": str(request_id),
                    "duration_ms": duration_ms,
                    "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                })
                return UserResponse(
                    request_id=request_id,
                    text=fast_result,
                    source=request.source,
                    duration_ms=duration_ms,
                )

            # Stage 1: Request pipeline — build context, compile prompt
            context_result = await self._request_pipeline.process(request)

            # Stage 2: LLM generation with tool calling
            response = await self._response_pipeline.generate(
                system_prompt=context_result.system_prompt,
                messages=context_result.messages,
                tool_defs=context_result.tool_defs,
                session_id=session_id,
            )

            # Stage 3: Store conversation turn in memory
            await self._store_turn(session_id, request.text, response.text)

            # Stage 4: Update session state
            await self._session_manager.update_session(
                session_id=session_id,
                user_text=request.text,
                assistant_text=response.text,
            )

            duration_ms = (self._get_time() - start_time) * 1000

            await self._emit_event("runtime.request_complete", {
                "session_id": session_id,
                "request_id": str(request_id),
                "duration_ms": duration_ms,
                "token_usage": {
                    "prompt_tokens": response.token_usage.prompt_tokens,
                    "completion_tokens": response.token_usage.completion_tokens,
                    "total_tokens": response.token_usage.total_tokens,
                },
            })

            return UserResponse(
                request_id=request_id,
                text=response.text,
                source=request.source,
                duration_ms=duration_ms,
            )

        except Exception as exc:
            duration_ms = (self._get_time() - start_time) * 1000
            self._logger.error("Runtime error: %s", exc)

            await self._emit_event("runtime.request_error", {
                "session_id": session_id,
                "request_id": str(request_id),
                "error": str(exc),
                "duration_ms": duration_ms,
            })

            return UserResponse(
                request_id=request_id,
                text="An error occurred while processing your request.",
                source=request.source,
                duration_ms=duration_ms,
            )

    async def process_request_stream(
        self,
        request: UserRequest,
    ) -> AsyncIterator[str]:
        """Process a request and stream response tokens.

        Tool execution is handled transparently: if the LLM issues tool calls
        during streaming, they are executed and results fed back before
        streaming continues.

        Parameters
        ----------
        request : UserRequest
            The immutable inbound request.

        Yields
        ------
        str
            Successive text chunks from the LLM.

        Raises
        ------
        ModuleDegradedError
            If the runtime is in a degraded state.
        """
        self._ensure_not_degraded()

        request_id = request.id
        session_id = request.session_id
        start_time = self._get_time()

        await self._emit_event("runtime.request_start", {
            "session_id": session_id,
            "request_id": str(request_id),
            "source": request.source,
        })

        accumulated_text = ""

        try:
            # Stage 0: Fast Command Engine bypass check
            if self._fast_command_router and self._fast_command_router.is_fast_command(request.text):
                self._logger.info("Fast Command Router match: '%s' — executing directly", request.text)
                fast_result = await self._fast_command_router.execute_fast_command(request.text)
                duration_ms = (self._get_time() - start_time) * 1000

                yield fast_result

                await self._store_turn(session_id, request.text, fast_result)
                await self._session_manager.update_session(
                    session_id=session_id,
                    user_text=request.text,
                    assistant_text=fast_result,
                )
                await self._emit_event("runtime.request_complete", {
                    "session_id": session_id,
                    "request_id": str(request_id),
                    "duration_ms": duration_ms,
                    "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                })
                return

            # Stage 1: Request pipeline — build context, compile prompt
            context_result = await self._request_pipeline.process(request)

            # Stage 2: Stream with tool calling
            async for chunk in self._response_pipeline.generate_stream(
                system_prompt=context_result.system_prompt,
                messages=context_result.messages,
                tool_defs=context_result.tool_defs,
                session_id=session_id,
            ):
                accumulated_text += chunk
                yield chunk

            # Stage 3: Store conversation turn in memory
            token_usage = self._estimate_token_usage(
                context_result.system_prompt, accumulated_text
            )
            final_response = LLMResponse(
                text=accumulated_text,
                tool_calls=None,
                finish_reason="stop",
                token_usage=token_usage,
                provider="runtime_stream",
                duration_ms=(self._get_time() - start_time) * 1000,
            )
            await self._store_turn(session_id, request.text, final_response.text)

            # Stage 4: Update session state
            await self._session_manager.update_session(
                session_id=session_id,
                user_text=request.text,
                assistant_text=final_response.text,
            )

            duration_ms = (self._get_time() - start_time) * 1000

            await self._emit_event("runtime.request_complete", {
                "session_id": session_id,
                "request_id": str(request_id),
                "duration_ms": duration_ms,
                "token_usage": {
                    "prompt_tokens": token_usage.prompt_tokens,
                    "completion_tokens": token_usage.completion_tokens,
                    "total_tokens": token_usage.total_tokens,
                },
            })

        except Exception as exc:
            self._logger.error("Runtime stream error: %s", exc)
            await self._emit_event("runtime.request_error", {
                "session_id": session_id,
                "request_id": str(request_id),
                "error": str(exc),
            })
            yield f"\n[Error: {exc}]"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _store_turn(
        self,
        session_id: str,
        user_text: str,
        assistant_text: str,
    ) -> None:
        """Persist both sides of the conversation turn via MemoryManager."""
        if self._memory_manager is None:
            return
        try:
            await self._memory_manager.store_message(
                session_id,
                Message(role="user", content=user_text),
            )
            await self._memory_manager.store_message(
                session_id,
                Message(role="assistant", content=assistant_text),
            )
        except Exception as exc:
            self._logger.warning("Failed to persist messages: %s", exc)

    def _estimate_token_usage(
        self,
        prompt: str,
        response_text: str,
    ) -> TokenUsage:
        """Estimate token usage for streaming (rough heuristic)."""
        prompt_tokens = max(1, len(prompt) // 4)
        completion_tokens = max(1, len(response_text) // 4)
        return TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )

    async def _emit_event(self, event_type: str, data: dict[str, Any]) -> None:
        if self._event_bus is None:
            return
        emit = getattr(self._event_bus, "emit", None)
        if emit is not None:
            await emit(event_type, data)

    def _ensure_not_degraded(self) -> None:
        if self._degraded:
            raise ModuleDegradedError(
                "Runtime is degraded",
                context={"module": "runtime"},
            )

    @staticmethod
    def _get_time() -> float:
        import time
        return time.time()

    # ------------------------------------------------------------------
    # Properties for testing/debugging
    # ------------------------------------------------------------------

    @property
    def request_pipeline(self) -> RequestPipeline:
        return self._request_pipeline

    @property
    def response_pipeline(self) -> ResponsePipeline:
        return self._response_pipeline

    @property
    def tool_router(self) -> ToolRouter:
        return self._tool_router

    @property
    def context_router(self) -> ContextRouter:
        return self._request_pipeline.context_router

    @property
    def session_manager(self) -> SessionManager:
        return self._session_manager

    @property
    def message_dispatcher(self) -> MessageDispatcher:
        return self._message_dispatcher
