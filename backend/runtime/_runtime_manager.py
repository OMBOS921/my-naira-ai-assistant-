"""
RuntimeManager — end-to-end AI execution pipeline orchestrator.

Conforms to ``ModuleInterface`` (``backend/types.py``).
"""

from __future__ import annotations

import inspect
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from backend.exceptions import ModuleDegradedError
from backend.modules.analytics import AnalyticsEvent, EventType
from backend.modules.decision import RouteTarget
from backend.runtime._request_context import RequestContext
from backend.runtime._tool_loop import MAX_TOOL_ITERATIONS, run_tool_loop
from backend.runtime.fast_command_router import FastCommandRouter
from backend.types import (
    LLMResponse,
    Message,
    TokenUsage,
    ToolDef,
    UserRequest,
    UserResponse,
)

_LOG = logging.getLogger("naira.runtime")


class RuntimeManager:
    """Orchestrates the end-to-end AI execution pipeline.

    Owns the full request lifecycle:
    1. Decision & Routing resolution (via DecisionManager / FastCommandRouter)
    2. Task Planning for multi-step requests (via PlanningManager)
    3. Session resolution (via ConversationManager)
    4. Context assembly (via ContextManager)
    5. Prompt compilation (via PromptManager)
    6. LLM generation with tool calling (via LLMManager + ToolManager)
    7. Analytics event recording (via AnalyticsManager)
    8. Memory persistence (via MemoryManager)
    9. Streaming response generation
    10. Event emission (via EventBus)

    Conforms to ``ModuleInterface`` (``backend/types.py``).
    """

    def __init__(
        self,
        *,
        config: object | None = None,
        logger: logging.Logger | None = None,
        context_manager: object | None = None,
        prompt_manager: object | None = None,
        llm_manager: object | None = None,
        tool_manager: object | None = None,
        memory_manager: object | None = None,
        conversation_manager: object | None = None,
        context_intelligence_manager: object | None = None,
        pc_control_manager: object | None = None,
        decision_manager: object | None = None,
        analytics_manager: object | None = None,
        planning_manager: object | None = None,
        event_bus: object | None = None,
        max_tool_iterations: int = MAX_TOOL_ITERATIONS,
    ) -> None:
        self._config = config
        self._logger = logger or _LOG
        self._context_manager = context_manager
        self._prompt_manager = prompt_manager
        self._llm_manager = llm_manager
        self._tool_manager = tool_manager
        self._memory_manager = memory_manager
        self._conversation_manager = conversation_manager
        self._context_intelligence_manager = context_intelligence_manager
        self._pc_control_manager = pc_control_manager
        self._decision_manager = decision_manager
        self._analytics_manager = analytics_manager
        self._planning_manager = planning_manager
        self._event_bus = event_bus
        self._max_tool_iterations = max_tool_iterations
        self._degraded: bool = False
        self._initialized: bool = False

        self._fast_command_router = FastCommandRouter(
            pc_control_manager=pc_control_manager,
            logger=self._logger,
        )

        # Wire FastCommandRouter into DecisionManager if decision manager is supplied
        if self._decision_manager is not None and hasattr(
            self._decision_manager, "_fast_command_router"
        ):
            self._decision_manager._fast_command_router = self._fast_command_router

    # ------------------------------------------------------------------
    # Module lifecycle  (ModuleInterface protocol)
    # ------------------------------------------------------------------

    async def async_init(self) -> None:
        self._initialized = True
        self._logger.info("Runtime manager initialised")

    async def async_shutdown(self) -> None:
        self._degraded = False
        self._initialized = False
        self._logger.info("Runtime manager shut down.")

    def degrade(self) -> None:
        self._degraded = True
        self._logger.warning("Runtime manager marked degraded")

    @property
    def degraded(self) -> bool:
        return self._degraded

    @property
    def initialized(self) -> bool:
        return self._initialized

    # ------------------------------------------------------------------
    # Request processing
    # ------------------------------------------------------------------

    async def process_request(self, request: UserRequest) -> UserResponse:
        """Process a single user request end-to-end."""
        self._ensure_not_degraded()

        ctx = RequestContext(
            request_id=request.id,
            session_id=request.session_id,
            source=request.source,
            user_text=request.text,
            metadata=request.metadata,
            start_time=time.time(),
        )

        try:
            self._logger.info(
                "[ROUTING] process_request received — text=%r source=%s session=%s",
                request.text, request.source, request.session_id,
            )

            await self._emit_event("runtime.request_start", {
                "session_id": ctx.session_id,
                "request_id": str(ctx.request_id),
            })

            # Decision Engine Routing
            target_route = RouteTarget.LLM_CONVERSATION
            if self._decision_manager is not None:
                decide_fn = getattr(self._decision_manager, "decide", None)
                if callable(decide_fn):
                    decision = await decide_fn(request.text, request.metadata)
                    target_route = decision.target
                    self._logger.info(
                        "[ROUTING] DecisionManager target=%s confidence=%.2f reason=%s",
                        decision.target, decision.confidence, decision.reason,
                    )

            if (
                target_route == RouteTarget.LLM_CONVERSATION
                and self._fast_command_router is not None
                and self._fast_command_router.is_fast_command(request.text)
            ):
                target_route = RouteTarget.FAST_COMMAND_ROUTER

            # Route 1: FAST_COMMAND_ROUTER
            fcr = self._fast_command_router
            if target_route == RouteTarget.FAST_COMMAND_ROUTER and fcr is not None:
                self._logger.info(
                    "[ROUTING] [MATCH] Fast Command Router MATCHED: '%s'", request.text
                )
                fast_result = await fcr.execute_fast_command(request.text)
                duration_ms = (time.time() - ctx.start_time) * 1000

                if self._analytics_manager is not None:
                    rec_fn = getattr(self._analytics_manager, "record", None)
                    if callable(rec_fn):
                        rec_fn(
                            AnalyticsEvent(
                                event_type=EventType.FCR_HIT,
                                duration_ms=duration_ms,
                                success=True,
                                payload={"request": request.text, "target": "fcr"},
                            )
                        )

                token_usage = self._estimate_token_usage("", fast_result)
                final_response = LLMResponse(
                    text=fast_result,
                    tool_calls=None,
                    finish_reason="stop",
                    token_usage=token_usage,
                    provider="fast_command_router",
                    duration_ms=duration_ms,
                )
                await self._store_turn(ctx, final_response)
                return UserResponse(
                    request_id=request.id,
                    text=fast_result,
                    source=request.source,
                    duration_ms=duration_ms,
                )

            # Route 2: PLANNING_ENGINE
            if target_route == RouteTarget.PLANNING_ENGINE and self._planning_manager is not None:
                self._logger.info("[ROUTING] Routing request to PlanningEngine: %r", request.text)
                plan_fn = getattr(self._planning_manager, "plan", None)
                exec_plan_fn = getattr(self._planning_manager, "execute_plan", None)

                if callable(plan_fn) and callable(exec_plan_fn):
                    plan = await plan_fn(request.text, request.metadata)
                    plan_res = await exec_plan_fn(plan)
                    duration_ms = (time.time() - ctx.start_time) * 1000

                    step_cnt = len(plan_res.executed_steps)
                    if plan_res.success:
                        res_text = f"Executed multi-step plan successfully ({step_cnt} steps)."
                    else:
                        res_text = (
                            f"Plan execution failed at step {plan_res.failed_step}: "
                            f"{plan_res.error}"
                        )

                    if self._analytics_manager is not None:
                        rec_fn = getattr(self._analytics_manager, "record", None)
                        if callable(rec_fn):
                            rec_fn(
                                AnalyticsEvent(
                                    event_type=EventType.TOOL_CALL,
                                    duration_ms=duration_ms,
                                    success=plan_res.success,
                                    payload={"request": request.text, "plan_id": plan.plan_id},
                                )
                            )

                    token_usage = self._estimate_token_usage("", res_text)
                    final_response = LLMResponse(
                        text=res_text,
                        tool_calls=None,
                        finish_reason="stop",
                        token_usage=token_usage,
                        provider="planning_engine",
                        duration_ms=duration_ms,
                    )
                    await self._store_turn(ctx, final_response)
                    return UserResponse(
                        request_id=request.id,
                        text=res_text,
                        source=request.source,
                        duration_ms=duration_ms,
                    )

            # Route 3: Standard LLM_CONVERSATION
            self._logger.info(
                "[ROUTING] Falling through to LLM conversation pipeline for text=%r", request.text
            )

            if self._analytics_manager is not None:
                rec_fn = getattr(self._analytics_manager, "record", None)
                if callable(rec_fn):
                    rec_fn(
                        AnalyticsEvent(
                            event_type=EventType.LLM_FALLBACK,
                            duration_ms=0.0,
                            success=True,
                            payload={"request": request.text},
                        )
                    )

            ctx.current_stage = "session"
            await self._resolve_session(ctx)

            ctx.current_stage = "context"
            ctx.system_prompt = self._compile_prompt()
            ctx.messages = self._build_context(ctx).messages[:]

            ctx.current_stage = "llm"
            tool_defs = self._get_tool_defs()
            response = await self._generate_with_tools(
                ctx.system_prompt,
                ctx.messages,
                tool_defs,
            )

            ctx.current_stage = "memory"
            await self._store_turn(ctx, response)

            ctx.current_stage = "emit"
            duration_ms = (time.time() - ctx.start_time) * 1000

            await self._emit_event("runtime.request_complete", {
                "session_id": ctx.session_id,
                "request_id": str(ctx.request_id),
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
            duration_ms = (time.time() - ctx.start_time) * 1000
            self._logger.error(
                "Runtime error at stage '%s': %s", ctx.current_stage, exc
            )

            await self._emit_event("runtime.request_error", {
                "session_id": ctx.session_id,
                "request_id": str(ctx.request_id),
                "error": str(exc),
                "stage": ctx.current_stage,
            })

            return UserResponse(
                request_id=request.id,
                text="An error occurred while processing your request.",
                source=request.source,
                duration_ms=duration_ms,
            )

    async def process_request_stream(
        self,
        request: UserRequest,
    ) -> AsyncIterator[str]:
        """Process a request and stream the response tokens."""
        self._ensure_not_degraded()

        ctx = RequestContext(
            request_id=request.id,
            session_id=request.session_id,
            source=request.source,
            user_text=request.text,
            metadata=request.metadata,
            start_time=time.time(),
        )

        try:
            self._logger.info(
                "[ROUTING] process_request_stream received -- text=%r source=%s session=%s",
                request.text, request.source, request.session_id,
            )

            await self._emit_event("runtime.request_start", {
                "session_id": ctx.session_id,
                "request_id": str(ctx.request_id),
            })

            # Stage 0: Decision Engine Routing
            target_route = RouteTarget.LLM_CONVERSATION
            if self._decision_manager is not None:
                decide_fn = getattr(self._decision_manager, "decide", None)
                if callable(decide_fn):
                    decision = await decide_fn(request.text, request.metadata)
                    target_route = decision.target

            if (
                target_route == RouteTarget.LLM_CONVERSATION
                and self._fast_command_router is not None
                and self._fast_command_router.is_fast_command(request.text)
            ):
                target_route = RouteTarget.FAST_COMMAND_ROUTER

            fcr = self._fast_command_router
            if target_route == RouteTarget.FAST_COMMAND_ROUTER and fcr is not None:
                self._logger.info(
                    "[ROUTING] [MATCH] Fast Command Router MATCHED (stream): '%s'", request.text
                )
                fast_result = await fcr.execute_fast_command(request.text)
                duration_ms = (time.time() - ctx.start_time) * 1000

                yield fast_result

                token_usage = self._estimate_token_usage("", fast_result)
                final_response = LLMResponse(
                    text=fast_result,
                    tool_calls=None,
                    finish_reason="stop",
                    token_usage=token_usage,
                    provider="fast_command_router",
                    duration_ms=duration_ms,
                )
                await self._store_turn(ctx, final_response)
                return

            await self._resolve_session(ctx)

            ctx.system_prompt = self._compile_prompt()
            ctx.messages = self._build_context(ctx).messages[:]
            tool_defs = self._get_tool_defs()

            accumulated_text = ""

            async for chunk in self._stream_with_tools(
                ctx.system_prompt,
                ctx.messages,
                tool_defs,
            ):
                accumulated_text += chunk
                yield chunk

            token_usage = self._estimate_token_usage(
                ctx.system_prompt, accumulated_text
            )
            final_response = LLMResponse(
                text=accumulated_text,
                tool_calls=None,
                finish_reason="stop",
                token_usage=token_usage,
                provider="runtime_stream",
                duration_ms=(time.time() - ctx.start_time) * 1000,
            )

            await self._store_turn(ctx, final_response)

        except Exception as exc:
            self._logger.error(
                "Runtime stream error at stage '%s': %s", ctx.current_stage, exc
            )
            yield f"\n[Error: {exc}]"

    # ------------------------------------------------------------------
    # Pipeline stages
    # ------------------------------------------------------------------

    async def _resolve_session(self, ctx: RequestContext) -> object:
        """Resolve the session via the conversation manager."""
        if self._conversation_manager is None:
            return None

        resolve = getattr(self._conversation_manager, "process_request", None)
        if callable(resolve):
            try:
                req = UserRequest(
                    id=ctx.request_id,
                    session_id=ctx.session_id,
                    text=ctx.user_text,
                    source=ctx.source,
                    metadata=ctx.metadata,
                )
                try:
                    result = resolve(req)
                except TypeError:
                    try:
                        result = resolve(ctx)
                    except TypeError:
                        result = resolve(ctx.session_id)

                if inspect.isawaitable(result):
                    result = await result
                return result
            except Exception as exc:
                self._logger.warning(
                    "ConversationManager process_request failed: %s", exc
                )

        route = getattr(self._conversation_manager, "router", None)
        if route is not None:
            route_fn = getattr(route, "route", None)
            if callable(route_fn):
                try:
                    result = route_fn(ctx.session_id)
                    if inspect.isawaitable(result):
                        result = await result
                    return result
                except Exception as exc:
                    self._logger.warning(
                        "ConversationManager router route failed: %s", exc
                    )
        return None

    def _compile_prompt(self) -> str:
        """Compile the system prompt via PromptManager."""
        if self._prompt_manager is None:
            return ""
        compile_fn = getattr(self._prompt_manager, "compile", None)
        if compile_fn is not None:
            return compile_fn()
        return ""

    def _build_context(self, ctx: RequestContext) -> object:
        """Build context via ContextManager."""
        if self._context_manager is None:
            return _empty_context()
        build = getattr(self._context_manager, "build_context", None)
        if build is not None:
            return build(ctx.session_id, ctx.user_text, ctx.system_prompt)
        return _empty_context()

    def _get_tool_defs(self) -> list[ToolDef]:
        """Fetch tool definitions from the ToolManager."""
        if self._tool_manager is None:
            return []
        get_defs = getattr(self._tool_manager, "get_tool_defs", None)
        if get_defs is not None:
            return get_defs()
        return []

    async def _generate_with_tools(
        self,
        system_prompt: str,
        context_messages: list[Message],
        tool_defs: list[ToolDef],
    ) -> LLMResponse:
        """Generate an LLM response with optional tool calling loop."""
        if self._llm_manager is None:
            return _empty_llm_response()

        if tool_defs:
            return await run_tool_loop(
                llm_manager=self._llm_manager,
                tool_manager=self._tool_manager,
                system_prompt=system_prompt,
                context_messages=context_messages,
                tool_defs=tool_defs,
            )

        generate = getattr(self._llm_manager, "generate", None)
        if generate is not None:
            return await generate(system_prompt, context_messages)
        return _empty_llm_response()

    async def _stream_with_tools(
        self,
        system_prompt: str,
        context_messages: list[Message],
        tool_defs: list[ToolDef],
    ) -> AsyncIterator[str]:
        """Stream response tokens with native multi-iteration tool execution."""
        if self._llm_manager is None:
            yield "Action failed"
            return

        generate_fn = getattr(self._llm_manager, "generate", None)
        if generate_fn is None:
            yield "Action failed"
            return

        iterations = 0
        final_text_yielded = False

        while iterations < self._max_tool_iterations:
            iterations += 1
            try:
                response: LLMResponse = await generate_fn(
                    prompt=system_prompt,
                    context=context_messages,
                    tools=tool_defs if tool_defs else None,
                )
            except Exception as exc:
                self._logger.error(
                    "LLM generation error in stream loop (iter %d): %s", iterations, exc
                )
                if not final_text_yielded:
                    yield "Action failed"
                return

            if response.tool_calls:
                assistant_msg = Message(
                    role="assistant",
                    content=response.text or "",
                    tool_calls=response.tool_calls,
                )
                context_messages.append(assistant_msg)

                for tc in response.tool_calls:
                    res_content = "Tool executed successfully."
                    if self._tool_manager is not None:
                        try:
                            tool_res = await self._tool_manager.execute_tool_call(tc)
                            if hasattr(tool_res, "result") and tool_res.result is not None:
                                res_content = (
                                    json.dumps(tool_res.result)
                                    if isinstance(tool_res.result, (dict, list))
                                    else str(tool_res.result)
                                )
                            elif hasattr(tool_res, "error") and tool_res.error:
                                res_content = f"Error: {tool_res.error}"
                        except Exception as tool_exc:
                            self._logger.error("Tool execution error: %s", tool_exc)
                            res_content = f"Tool execution failed: {tool_exc}"

                    context_messages.append(
                        Message(
                            role="tool",
                            content=res_content,
                            tool_call_id=tc.id,
                        )
                    )
                continue
            else:
                text_content = response.text or ""
                if text_content.strip():
                    yield text_content
                    final_text_yielded = True
                else:
                    yield "Action executed successfully."
                    final_text_yielded = True
                return

        if not final_text_yielded:
            yield "Action executed successfully."

    async def _store_turn(
        self,
        ctx: RequestContext,
        response: LLMResponse,
    ) -> None:
        """Persist both sides of the conversation turn."""
        asst_text = (
            response.text if (response and response.text) else "Action executed successfully."
        )

        if self._context_manager is not None:
            add_asst = getattr(self._context_manager, "add_assistant_message", None)
            if add_asst is not None:
                try:
                    add_asst(ctx.session_id, asst_text)
                except Exception as exc:
                    self._logger.warning("Failed to store assistant message in context: %s", exc)

        if self._memory_manager is None:
            return
        store = getattr(self._memory_manager, "store_message", None)
        if store is None:
            return
        try:
            await store(
                ctx.session_id,
                Message(role="user", content=ctx.user_text),
            )
            await store(
                ctx.session_id,
                Message(role="assistant", content=asst_text),
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
            raise ModuleDegradedError(
                "RuntimeManager is degraded",
                context={"module": "runtime"},
            )


def _empty_context() -> object:
    return type("EmptyContext", (), {"messages": [], "system_prompt": ""})()


def _empty_llm_response() -> LLMResponse:
    return LLMResponse(
        text="",
        tool_calls=None,
        finish_reason="error",
        token_usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        provider="none",
        duration_ms=0.0,
    )
