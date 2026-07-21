"""
ToolCallingEngine — dedicated layer for automatic tool call detection,
routing, execution, and iterative LLM reflection.

Owns the complete tool-calling sub-loop:
  1. Detect tool calls in the LLM response
  2. Validate tool existence, permissions, enabled state
  3. Execute through ToolRouter → ToolManager
  4. Capture ToolResult for each call
  5. Feed results back into the Runtime
  6. Rebuild context after every tool result
  7. Update conversation history after every tool result
  8. Repeat until the LLM returns a text-only response
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any

from backend.orchestrator import EventBus
from backend.runtime.tool_router import ToolRouter
from backend.types import LLMResponse, Message, TokenUsage, ToolCall, ToolDef

_LOG = logging.getLogger("naira.runtime.tool_calling_engine")

_DEFAULT_MAX_ITERATIONS: int = 10
_DEFAULT_TIMEOUT_SECONDS: float = 300.0


@dataclass(frozen=True)
class ToolCallingResult:
    """Result of a complete tool-calling session.

    Attributes
    ----------
    response : LLMResponse
        The final LLM response (text only, no tool calls).
    iterations : int
        Number of LLM calls made (including the final one).
    tool_calls_executed : int
        Total number of individual tool calls executed.
    """

    response: LLMResponse
    iterations: int
    tool_calls_executed: int


@dataclass
class ToolCallingStats:
    """Mutable stats accumulator for a single tool-calling session."""

    iterations: int = 0
    tool_calls_executed: int = 0
    loop_start_time: float = 0.0
    cancelled: bool = False


class ToolCallingEngine:
    """Orchestrates the tool-calling sub-loop within the Runtime pipeline.

    This is a **dedicated Tool Calling layer** that:

    - Parses tool calls from LLM responses.
    - Validates tool existence, permissions, and enabled state.
    - Executes through ToolRouter → ToolManager.
    - Captures ``ToolResult`` for every call.
    - Feeds results back into the Runtime loop.
    - Rebuilds context after each tool execution round.
    - Updates conversation history after each tool execution round.
    - Emits ``EventBus`` events at every stage.
    - Enforces maximum iteration, recursion, and timeout limits.
    - Supports graceful cancellation.
    - Handles partial failures without crashing the Runtime.

    Parameters
    ----------
    llm_manager : object | None
        LLMManager instance with ``generate(prompt, context, tools)``.
    tool_router : ToolRouter | None
        ToolRouter instance for tool execution.
    conversation_manager : object | None
        ConversationManager instance for session history updates.
    context_manager : object | None
        ContextManager instance for context rebuilding after tool results.
    event_bus : EventBus | None
        EventBus for event emission at every stage.
    max_iterations : int
        Maximum LLM-invocation iterations (default 10).
    timeout_seconds : float
        Total wall-clock timeout for the tool-calling loop (default 300).
    logger : logging.Logger | None
        Module-scoped logger.
    """

    def __init__(
        self,
        *,
        llm_manager: object | None = None,
        tool_router: ToolRouter | None = None,
        conversation_manager: object | None = None,
        context_manager: object | None = None,
        event_bus: EventBus | None = None,
        max_iterations: int = _DEFAULT_MAX_ITERATIONS,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        logger: logging.Logger | None = None,
    ) -> None:
        self._llm_manager = llm_manager
        self._tool_router = tool_router or ToolRouter()
        self._conversation_manager = conversation_manager
        self._context_manager = context_manager
        self._event_bus = event_bus
        self._max_iterations = max_iterations
        self._timeout_seconds = timeout_seconds
        self._logger = logger or _LOG
        self._degraded: bool = False
        self._initialized: bool = False

        # Cancellation support
        self._cancel_event: asyncio.Event = asyncio.Event()

    # ------------------------------------------------------------------
    # Module lifecycle
    # ------------------------------------------------------------------

    async def async_init(self) -> None:
        """Initialise the tool calling engine."""
        if self._tool_router is not None:
            await self._tool_router.async_init()
        self._initialized = True
        self._logger.debug("Tool calling engine initialised")

    async def async_shutdown(self) -> None:
        """Release resources."""
        if self._tool_router is not None:
            await self._tool_router.async_shutdown()
        self._degraded = False
        self._initialized = False
        self._logger.debug("Tool calling engine shut down")

    def degrade(self) -> None:
        """Mark as degraded."""
        self._degraded = True
        if self._tool_router is not None:
            self._tool_router.degrade()
        self._logger.warning("Tool calling engine marked degraded")

    @property
    def degraded(self) -> bool:
        return self._degraded

    @property
    def initialized(self) -> bool:
        return self._initialized

    # ------------------------------------------------------------------
    # Cancellation API
    # ------------------------------------------------------------------

    def cancel(self) -> None:
        """Request graceful cancellation of the current tool-calling loop."""
        self._cancel_event.set()
        self._logger.info("Tool calling engine cancellation requested")

    def reset_cancellation(self) -> None:
        """Reset the cancellation flag for a new invocation."""
        self._cancel_event.clear()

    # ------------------------------------------------------------------
    # Public execution API
    # ------------------------------------------------------------------

    async def execute(
        self,
        system_prompt: str,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> ToolCallingResult:
        """Run the complete tool-calling loop.

        Parameters
        ----------
        system_prompt : str
            Compiled system prompt for each LLM round.
        messages : list[Message]
            Current conversation messages (mutated in-place with assistant
            and tool result messages).
        tool_defs : list[ToolDef]
            Available tool definitions for the LLM.
        session_id : str
            Session identifier for event correlation and history updates.

        Returns
        -------
        ToolCallingResult
            Final response and execution statistics.

        Raises
        ------
        RuntimeError
            If the engine is degraded.
        """
        if self._degraded:
            raise RuntimeError("ToolCallingEngine is degraded")

        stats = ToolCallingStats()

        # If cancellation was requested before this call, return immediately
        if self._cancel_event.is_set():
            self._logger.info("Tool calling loop cancelled before execution started")
            await self._emit_event("tool_calling.cancelled", {
                "session_id": session_id,
                "iteration": 0,
            })
            return ToolCallingResult(
                response=self._empty_response(),
                iterations=0,
                tool_calls_executed=0,
            )

        self.reset_cancellation()

        await self._emit_event("tool_calling.start", {
            "session_id": session_id,
            "message_count": len(messages),
            "tool_count": len(tool_defs),
            "max_iterations": self._max_iterations,
            "timeout_seconds": self._timeout_seconds,
        })

        try:
            result = await self._run_loop(
                system_prompt=system_prompt,
                messages=messages,
                tool_defs=tool_defs,
                session_id=session_id,
                stats=stats,
            )
        except Exception as exc:
            self._logger.error("Tool calling loop failed: %s", exc)
            await self._emit_event("tool_calling.error", {
                "session_id": session_id,
                "error": str(exc),
                "iterations": stats.iterations,
                "tool_calls_executed": stats.tool_calls_executed,
            })
            raise

        await self._emit_event("tool_calling.complete", {
            "session_id": session_id,
            "iterations": stats.iterations,
            "tool_calls_executed": stats.tool_calls_executed,
            "finish_reason": result.response.finish_reason,
            "total_tokens": result.response.token_usage.total_tokens,
        })

        return result

    async def execute_stream(
        self,
        system_prompt: str,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
    ) -> AsyncIterator[str]:
        """Run the tool-calling loop with streaming.

        Yields text chunks from the LLM.  When tool calls are detected,
        they are executed transparently and the loop continues.

        Parameters
        ----------
        system_prompt : str
            Compiled system prompt.
        messages : list[Message]
            Current conversation messages (mutated in-place).
        tool_defs : list[ToolDef]
            Available tool definitions.
        session_id : str
            Session identifier.

        Yields
        ------
        str
            Successive text chunks from the LLM.
        """
        if self._degraded:
            yield ""
            return

        stats = ToolCallingStats()

        # If cancellation was requested before this call, return immediately
        if self._cancel_event.is_set():
            self._logger.info("Stream tool calling cancelled before execution started")
            await self._emit_event("tool_calling.cancelled", {
                "session_id": session_id,
                "iteration": 0,
            })
            return

        self.reset_cancellation()

        await self._emit_event("tool_calling.stream_start", {
            "session_id": session_id,
            "message_count": len(messages),
            "tool_count": len(tool_defs),
        })

        tool_defs_for_llm = tool_defs if tool_defs else None
        current_messages = messages[:]

        for iteration in range(1, self._max_iterations + 1):
            stats.iterations = iteration

            if self._cancel_event.is_set():
                self._logger.info("Tool calling loop cancelled at iteration %d", iteration)
                await self._emit_event("tool_calling.cancelled", {
                    "session_id": session_id,
                    "iteration": iteration,
                })
                return

            await self._emit_event("tool_calling.llm_stream_start", {
                "session_id": session_id,
                "iteration": iteration,
            })

            collected_text = ""
            tool_calls_detected: list[Any] = []

            if self._llm_manager is None:
                yield ""
                return

            generate_stream = getattr(self._llm_manager, "generate_stream", None)
            if generate_stream is None:
                yield ""
                return

            async for chunk in generate_stream(
                system_prompt,
                current_messages,
                tool_defs_for_llm,
            ):
                if self._cancel_event.is_set():
                    return
                yield chunk
                collected_text += chunk

            await self._emit_event("tool_calling.llm_stream_complete", {
                "session_id": session_id,
                "iteration": iteration,
                "collected_length": len(collected_text),
            })

            # Check for tool calls in the accumulated messages
            if current_messages and current_messages[-1].tool_calls:
                tool_calls_detected = current_messages[-1].tool_calls

            if tool_calls_detected:
                await self._emit_event("tool_calling.stream_tool_calls_detected", {
                    "session_id": session_id,
                    "iteration": iteration,
                    "tool_call_count": len(tool_calls_detected),
                })

                assistant_msg = Message(
                    role="assistant",
                    content=collected_text,
                    tool_calls=tool_calls_detected,
                )
                current_messages.append(assistant_msg)

                tool_result_messages = await self._execute_batch(
                    tool_calls=tool_calls_detected,
                    session_id=session_id,
                    stats=stats,
                )
                current_messages.extend(tool_result_messages)

                # Update conversation history first
                await self._update_conversation_history(
                    session_id, assistant_msg, tool_result_messages,
                )

                # Rebuild context after tool results
                await self._rebuild_context(session_id, current_messages, system_prompt)

                continue

            return

        self._logger.warning(
            "Stream tool loop reached max iterations (%d) for session %s",
            self._max_iterations,
            session_id,
        )
        await self._emit_event("tool_calling.stream_max_iterations", {
            "session_id": session_id,
            "max_iterations": self._max_iterations,
        })

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    async def _run_loop(
        self,
        system_prompt: str,
        messages: list[Message],
        tool_defs: list[ToolDef],
        session_id: str,
        stats: ToolCallingStats,
    ) -> ToolCallingResult:
        """Core non-streaming tool-calling loop."""
        tool_defs_for_llm = tool_defs if tool_defs else None
        previous_tool_signatures: set[str] = set()
        consecutive_identical: int = 0

        for iteration in range(1, self._max_iterations + 1):
            stats.iterations = iteration

            if self._cancel_event.is_set():
                self._logger.info("Tool calling loop cancelled at iteration %d", iteration)
                await self._emit_event("tool_calling.cancelled", {
                    "session_id": session_id,
                    "iteration": iteration,
                })
                return ToolCallingResult(
                    response=self._empty_response(),
                    iterations=iteration,
                    tool_calls_executed=stats.tool_calls_executed,
                )

            await self._emit_event("tool_calling.llm_generation_start", {
                "session_id": session_id,
                "iteration": iteration,
                "message_count": len(messages),
            })

            if self._llm_manager is None:
                return ToolCallingResult(
                    response=self._empty_response(),
                    iterations=iteration,
                    tool_calls_executed=stats.tool_calls_executed,
                )

            generate = getattr(self._llm_manager, "generate", None)
            if generate is None:
                return ToolCallingResult(
                    response=self._empty_response(),
                    iterations=iteration,
                    tool_calls_executed=stats.tool_calls_executed,
                )

            try:
                response = await asyncio.wait_for(
                    generate(
                        prompt=system_prompt,
                        context=messages,
                        tools=tool_defs_for_llm,
                    ),
                    timeout=self._timeout_seconds,
                )
            except asyncio.TimeoutError:
                self._logger.error(
                    "LLM generation timed out after %ds (iteration %d)",
                    self._timeout_seconds,
                    iteration,
                )
                await self._emit_event("tool_calling.llm_timeout", {
                    "session_id": session_id,
                    "iteration": iteration,
                    "timeout_seconds": self._timeout_seconds,
                })
                return ToolCallingResult(
                    response=self._empty_response(),
                    iterations=iteration,
                    tool_calls_executed=stats.tool_calls_executed,
                )

            await self._emit_event("tool_calling.llm_generation_complete", {
                "session_id": session_id,
                "iteration": iteration,
                "provider": response.provider,
                "finish_reason": response.finish_reason,
                "has_tool_calls": bool(response.tool_calls),
                "token_usage": response.token_usage.total_tokens,
            })

            # No tool calls — final answer
            if not response.tool_calls:
                return ToolCallingResult(
                    response=response,
                    iterations=iteration,
                    tool_calls_executed=stats.tool_calls_executed,
                )

            # Recursion protection: detect repeated identical tool call sets
            current_sig = self._tool_call_signature(response.tool_calls)
            if current_sig in previous_tool_signatures:
                consecutive_identical += 1
            else:
                consecutive_identical = 0
            previous_tool_signatures.add(current_sig)

            if consecutive_identical >= 2:
                self._logger.warning(
                    "Recursion protection triggered — same tool calls %d consecutive times",
                    consecutive_identical,
                )
                await self._emit_event("tool_calling.recursion_protection", {
                    "session_id": session_id,
                    "iteration": iteration,
                    "tool_call_signature": current_sig,
                })
                return ToolCallingResult(
                    response=response,
                    iterations=iteration,
                    tool_calls_executed=stats.tool_calls_executed,
                )

            # Execute tool calls
            await self._emit_event("tool_calling.tool_calls_detected", {
                "session_id": session_id,
                "iteration": iteration,
                "tool_call_count": len(response.tool_calls),
                "tool_names": [tc.name for tc in response.tool_calls],
            })

            assistant_msg = Message(
                role="assistant",
                content=response.text,
                tool_calls=response.tool_calls,
            )
            messages.append(assistant_msg)

            tool_result_messages = await self._execute_batch(
                tool_calls=response.tool_calls,
                session_id=session_id,
                stats=stats,
            )
            messages.extend(tool_result_messages)

            # Update conversation history first
            await self._update_conversation_history(
                session_id, assistant_msg, tool_result_messages,
            )

            # Rebuild context after tool results
            await self._rebuild_context(session_id, messages, system_prompt)

        # Max iterations reached
        self._logger.warning(
            "Tool calling loop reached max iterations (%d) for session %s",
            self._max_iterations,
            session_id,
        )
        await self._emit_event("tool_calling.max_iterations_reached", {
            "session_id": session_id,
            "max_iterations": self._max_iterations,
            "tool_calls_executed": stats.tool_calls_executed,
        })

        return ToolCallingResult(
            response=response,
            iterations=self._max_iterations,
            tool_calls_executed=stats.tool_calls_executed,
        )

    async def _execute_batch(
        self,
        tool_calls: Sequence[ToolCall],
        session_id: str,
        stats: ToolCallingStats,
    ) -> list[Message]:
        """Execute a batch of tool calls and return result messages.

        Each tool call is executed independently; partial failures are
        captured as error messages rather than propagated.
        """
        if not tool_calls:
            return []

        stats.tool_calls_executed += len(tool_calls)

        await self._emit_event("tool_calling.batch_execution_start", {
            "session_id": session_id,
            "tool_call_count": len(tool_calls),
            "tool_names": [tc.name for tc in tool_calls],
        })

        if self._tool_router is None:
            self._logger.warning("No ToolRouter available — skipping tool execution")
            return [
                Message(
                    role="tool",
                    content="Error: tool system unavailable",
                    tool_call_id=tc.id,
                )
                for tc in tool_calls
            ]

        try:
            result_messages = await self._tool_router.execute_tool_calls(
                tool_calls=tool_calls,
                session_id=session_id,
            )
        except Exception as exc:
            self._logger.error("Batch tool execution failed: %s", exc)
            await self._emit_event("tool_calling.batch_execution_error", {
                "session_id": session_id,
                "error": str(exc),
            })
            return [
                Message(
                    role="tool",
                    content=f"Error: tool execution failed — {exc}",
                    tool_call_id=tc.id,
                )
                for tc in tool_calls
            ]

        await self._emit_event("tool_calling.batch_execution_complete", {
            "session_id": session_id,
            "result_count": len(result_messages),
        })

        return result_messages

    # ------------------------------------------------------------------
    # Context and conversation management
    # ------------------------------------------------------------------

    async def _rebuild_context(
        self,
        session_id: str,
        messages: list[Message],
        system_prompt: str,
    ) -> None:
        """Rebuild the context after tool results are added.

        Applies sliding-window truncation on the session without
        injecting empty user messages or discarding existing messages.
        """
        if self._context_manager is None:
            return

        try:
            get_session = getattr(self._context_manager, "get_session", None)
            if get_session is not None:
                conv = get_session(session_id)
                if conv is not None:
                    apply_sliding = getattr(conv, "apply_sliding_window", None)
                    if apply_sliding is not None:
                        apply_sliding()
        except Exception as exc:
            self._logger.warning("Context rebuild failed: %s", exc)

        await self._emit_event("tool_calling.context_rebuilt", {
            "session_id": session_id,
            "message_count": len(messages),
        })

    async def _update_conversation_history(
        self,
        session_id: str,
        assistant_msg: Message,
        tool_result_messages: list[Message],
    ) -> None:
        """Persist assistant and tool result messages to conversation history."""
        if self._conversation_manager is None:
            return

        store = getattr(self._conversation_manager, "bridge", None)
        if store is not None:
            store_msg = getattr(store, "store_message", None)
            if store_msg is not None:
                try:
                    await store_msg(session_id, assistant_msg)
                    for tr_msg in tool_result_messages:
                        await store_msg(session_id, tr_msg)
                except Exception as exc:
                    self._logger.warning("Failed to persist tool messages: %s", exc)

        await self._emit_event("tool_calling.conversation_updated", {
            "session_id": session_id,
            "message_count": 1 + len(tool_result_messages),
        })

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
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _tool_call_signature(tool_calls: Sequence[ToolCall]) -> str:
        """Produce a deterministic signature for a set of tool calls.

        Used for recursion detection: if the exact same tool calls
        appear repeatedly, the engine breaks the loop.
        """
        parts = sorted(f"{tc.name}({dict(sorted(tc.arguments.items()))})" for tc in tool_calls)
        return "|".join(parts)

    @staticmethod
    def _empty_response() -> LLMResponse:
        """Return a minimal empty LLMResponse for error/fallback paths."""
        return LLMResponse(
            text="",
            tool_calls=None,
            finish_reason="error",
            token_usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
            provider="tool_calling_engine",
            duration_ms=0.0,
        )
