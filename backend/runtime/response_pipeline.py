"""
ResponsePipeline — handles LLM generation with tool calling loop.

Orchestrates:
1. LLM generation (via LLMManager)
2. Tool execution loop (via ToolCallingEngine)
3. Streaming support with transparent tool handling
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from backend.modules.llm import LLMManager
from backend.orchestrator import EventBus
from backend.runtime._tool_calling_engine import ToolCallingEngine
from backend.runtime.tool_router import ToolRouter
from backend.types import Message, ToolDef
_LOG = logging.getLogger("naira.runtime.response_pipeline")

MAX_TOOL_ITERATIONS: int = 10


@dataclass(frozen=True)
class GenerationResult:
    """Result of LLM generation with optional tool calls.

    Attributes
    ----------
    response : Any
        The complete LLM response (text, tool calls, metadata).
    """

    response: Any


class ResponsePipeline:
    """Generates LLM responses with optional tool calling loop.

    Supports both single-shot generation and streaming.  In streaming mode,
    tool calls are detected and executed transparently before continuing
    the stream.

    Parameters
    ----------
    llm_manager : LLMManager | None
        LLMManager instance for response generation.
    tool_router : ToolRouter | None
        ToolRouter instance for tool execution.
    max_tool_iterations : int
        Maximum iterations for the tool-calling loop (default 10).
    event_bus : EventBus | None
        EventBus for stage event emission.
    logger : logging.Logger | None
        Module-scoped logger.
    """

    def __init__(
        self,
        *,
        llm_manager: LLMManager | None = None,
        tool_router: ToolRouter | None = None,
        tool_calling_engine: ToolCallingEngine | None = None,
        max_tool_iterations: int = MAX_TOOL_ITERATIONS,
        event_bus: EventBus | None = None,
        logger: logging.Logger | None = None,
        conversation_manager: object | None = None,
        context_manager: object | None = None,
    ) -> None:
        self._llm_manager = llm_manager
        self._tool_router = tool_router or ToolRouter(
            llm_manager=llm_manager,
            event_bus=event_bus,
            logger=logger,
        )
        self._tool_calling_engine = tool_calling_engine or ToolCallingEngine(
            llm_manager=llm_manager,
            tool_router=self._tool_router,
            conversation_manager=conversation_manager,
            context_manager=context_manager,
            event_bus=event_bus,
            max_iterations=max_tool_iterations,
            logger=logger,
        )
        self._max_tool_iterations = max_tool_iterations
        self._event_bus = event_bus
        self._logger = logger or _LOG
        self._degraded: bool = False
        self._initialized: bool = False

    # ------------------------------------------------------------------
    # Module lifecycle
    # ------------------------------------------------------------------

    async def async_init(self) -> None:
        """Initialise the response pipeline."""
        await self._tool_router.async_init()
        await self._tool_calling_engine.async_init()
        self._initialized = True
        self._logger.debug("Response pipeline initialised")

    async def async_shutdown(self) -> None:
        """Release resources."""
        await self._tool_calling_engine.async_shutdown()
        await self._tool_router.async_shutdown()
        self._degraded = False
        self._initialized = False
        self._logger.debug("Response pipeline shut down")

    def degrade(self) -> None:
        """Mark as degraded."""
        self._degraded = True
        self._tool_router.degrade()
        self._tool_calling_engine.degrade()
        self._logger.warning("Response pipeline marked degraded")

    @property
    def degraded(self) -> bool:
        return self._degraded

    @property
    def initialized(self) -> bool:
        return self._initialized

    # ------------------------------------------------------------------
    # Public API — Non-streaming
    # ------------------------------------------------------------------

    async def generate(
        self,
        system_prompt: str,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> Any:
        """Generate a complete response with tool calling loop.

        Parameters
        ----------
        system_prompt : str
            Compiled system prompt.
        messages : list[Message]
            Conversation history including current user message.
        tool_defs : list[ToolDef]
            Available tool definitions.
        session_id : str
            Session identifier for event correlation.

        Returns
        -------
        Any
            The final LLM response (no tool calls).
        """
        self._ensure_not_degraded()

        if self._llm_manager is None:
            return _empty_llm_response()

        current_messages = messages[:]

        result = await self._tool_calling_engine.execute(
            system_prompt=system_prompt,
            messages=current_messages,
            tool_defs=tool_defs,
            session_id=session_id,
        )

        # Sync tool result messages back to the caller
        if current_messages:
            messages[:] = current_messages

        return result.response

    # ------------------------------------------------------------------
    # Public API — Streaming
    # ------------------------------------------------------------------

    async def generate_stream(
        self,
        system_prompt: str,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> AsyncIterator[str]:
        """Stream response tokens with transparent tool execution.

        If the LLM issues tool calls during streaming, they are executed
        and results fed back to the LLM before streaming continues.

        Parameters
        ----------
        system_prompt : str
            Compiled system prompt.
        messages : list[Message]
            Conversation history.
        tool_defs : list[ToolDef]
            Available tool definitions.
        session_id : str
            Session identifier for event correlation.

        Yields
        ------
        str
            Successive text chunks from the LLM.
        """
        self._ensure_not_degraded()

        if self._llm_manager is None:
            yield ""
            return

        current_messages = messages[:]

        async for chunk in self._tool_calling_engine.execute_stream(
            system_prompt=system_prompt,
            messages=current_messages,
            tool_defs=tool_defs,
            session_id=session_id,
        ):
            yield chunk

        # Sync tool result messages back to the caller
        if current_messages:
            messages[:] = current_messages

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
                "ResponsePipeline is degraded",
                context={"module": "runtime.response_pipeline"},
            )

    # ------------------------------------------------------------------
    # Properties for testing/debugging
    # ------------------------------------------------------------------

    @property
    def tool_router(self) -> ToolRouter:
        return self._tool_router


def _empty_llm_response() -> Any:
    """Return a minimal Any for fallback paths."""
    return Any(
        text="",
        tool_calls=None,
        finish_reason="error",
        token_usage=Any(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        provider="none",
        duration_ms=0.0,
    )
