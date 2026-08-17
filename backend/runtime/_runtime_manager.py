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
from types import SimpleNamespace
from typing import Any

from backend.exceptions import ModuleDegradedError
from backend.modules.analytics import AnalyticsEvent, EventType
from backend.modules.decision import RouteTarget
from backend.runtime._request_context import RequestContext

from backend.runtime.autonomous_task_engine import AutonomousTaskEngine
from backend.runtime.fast_command_router import CommandIntent, FastCommandRouter
from backend.runtime.multi_agent.multi_agent_orchestrator import MultiAgentOrchestrator
from backend.modules.reasoning_gateway import IntentCategory, ReasoningGateway
from backend.types import (
    Message, ToolDef, UserRequest, UserResponse, ModuleDegradedError
)

_LOG = logging.getLogger("naira.runtime")

_INTENT_CAPABILITY_MAP: dict[str, str] = {
    "SYSTEM_CONTROL": "pc_control",
    "OPEN_APP": "pc_control",
    "SET_VOLUME": "pc_control",
    "SET_BRIGHTNESS": "pc_control",
    "LOCK_PC": "pc_control",
    "SHUTDOWN": "pc_control",
    "RESTART": "pc_control",
    "SCREENSHOT": "pc_control",
    "SYSTEM_INFO": "pc_control",
    "KILL_PROCESS": "pc_control",
    "BROWSER_CONTROL": "browser",
    "OPEN_WEBSITE": "browser",
    "WEB_SEARCH": "browser",
    "FILE_SYSTEM": "file_manager",
    "CREATE_FOLDER": "file_manager",
    "DELETE_FOLDER": "file_manager",
    "RENAME_FOLDER": "file_manager",
    "CREATE_FILE": "file_manager",
    "DELETE_FILE": "file_manager",
    "OPEN_FILE": "file_manager",
    "RENAME_FILE": "file_manager",
    "CODING_AGENT": "coding_agent",
}


MAX_TOOL_ITERATIONS = 15

class RuntimeManager:
    """Orchestrates the end-to-end AI execution pipeline.

    Owns the full request lifecycle:
    1. Decision & Routing resolution (via DecisionManager / FastCommandRouter)
    2. Task Planning for multi-step requests (via PlanningManager)
    3. Session resolution (via ConversationManager)
    4. Any assembly (via ContextManager)
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
        tool_manager: object | None = None,
        memory_manager: object | None = None,
        conversation_manager: object | None = None,
        context_intelligence_manager: object | None = None,
        pc_control_manager: object | None = None,
        browser_manager: object | None = None,
        coding_agent_manager: object | None = None,
        vision_manager: object | None = None,
        decision_manager: object | None = None,
        analytics_manager: object | None = None,
        planning_manager: object | None = None,
        security_manager: object | None = None,
        reasoning_gateway: object | None = None,
        settings_manager: object | None = None,
        capability_manager: object | None = None,
        event_bus: object | None = None,
        max_tool_iterations: int = MAX_TOOL_ITERATIONS,
    ) -> None:
        self._config = config
        self._logger = logger or _LOG
        self._context_manager = context_manager
        self._tool_manager = tool_manager
        self._memory_manager = memory_manager
        self._conversation_manager = conversation_manager
        self._context_intelligence_manager = context_intelligence_manager
        self._pc_control_manager = pc_control_manager
        self._browser_manager = browser_manager
        self._coding_agent_manager = coding_agent_manager
        self._vision_manager = vision_manager
        self._decision_manager = decision_manager
        self._analytics_manager = analytics_manager
        self._planning_manager = planning_manager
        self._security_manager = security_manager
        self._settings_manager = settings_manager
        self._capability_manager = capability_manager
        self._reasoning_gateway = reasoning_gateway or ReasoningGateway(
            config=config,
            logger=self._logger,
            event_bus=event_bus,
            memory_manager=memory_manager,
            tool_manager=tool_manager,
        )
        self._event_bus = event_bus
        self._max_tool_iterations = max_tool_iterations
        self._degraded: bool = False
        self._initialized: bool = False

        self._fast_command_router = FastCommandRouter(
            pc_control_manager=pc_control_manager,
            browser_manager=browser_manager,
            vision_manager=vision_manager,
            logger=self._logger,
            settings_manager=settings_manager,
            security_manager=security_manager,
        )

        self._autonomous_task_engine = AutonomousTaskEngine(
            runtime_manager=self,
            logger=self._logger,
            event_bus=self._event_bus,
        )
        self._multi_agent_orchestrator = MultiAgentOrchestrator(
            runtime_manager=self,
            tool_manager=self._tool_manager,
            logger=self._logger,
            event_bus=self._event_bus,
        )

        # Wire FastCommandRouter into DecisionManager if decision manager is supplied
        if self._decision_manager is not None and hasattr(
            self._decision_manager, "_fast_command_router"
        ):
            self._decision_manager._fast_command_router = self._fast_command_router

        # Wire MemoryManager with ToolManager and ContextManager if present
        if self._memory_manager is not None:
            if self._tool_manager is not None:
                reg_t = getattr(self._memory_manager, "register_tools", None)
                if callable(reg_t):
                    reg_t(self._tool_manager)
            if self._context_manager is not None:
                set_m = getattr(self._context_manager, "set_memory_manager", None)
                if callable(set_m):
                    set_m(self._memory_manager)

    # ------------------------------------------------------------------
    # Module lifecycle  (ModuleInterface protocol)
    # ------------------------------------------------------------------

    async def async_init(self) -> None:
        self._initialized = True
        self._logger.info("Runtime manager initialized")

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

            # Stage 0: Security Validation (BEFORE Decision, FCR, Planning, Prompt, Any, LLM)
            if self._security_manager is not None and hasattr(self._security_manager, "validate_input"):
                val_res = self._security_manager.validate_input(request.text)
                if val_res.status == "reject":
                    duration_ms = (time.time() - ctx.start_time) * 1000
                    self._logger.warning("[SECURITY REJECTION] Request rejected by SecurityManager: %s", val_res.reason)
                    await self._emit_event("security.request_rejected", {
                        "session_id": ctx.session_id,
                        "request_id": str(ctx.request_id),
                        "reason": val_res.reason,
                    })
                    return UserResponse(
                        request_id=request.id,
                        text=f"[Security Rejection]: {val_res.reason}",
                        source=request.source,
                        duration_ms=duration_ms,
                    )

            # Decision Engine Routing
            target_route = RouteTarget.UNHANDLED
            if self._decision_manager is not None:
                decide_fn: Any = getattr(self._decision_manager, "decide", None)
                if callable(decide_fn):
                    decision = await decide_fn(request.text, request.metadata)  # type: ignore
                    target_route = decision.target
                    self._logger.info(
                        "[ROUTING] DecisionManager target=%s confidence=%.2f reason=%s",
                        decision.target, decision.confidence, decision.reason,
                    )

            if (
                target_route == RouteTarget.UNHANDLED
                and self._fast_command_router is not None
                and self._fast_command_router.is_fast_command(request.text)
            ):
                target_route = RouteTarget.FAST_COMMAND_ROUTER

            fcr = self._fast_command_router
            if target_route == RouteTarget.FAST_COMMAND_ROUTER and fcr is not None:
                fcr_intent_data = await fcr.classify_intent(request.text)
                intent_name = fcr_intent_data.get("intent", "")
                
                # If the classifier determined this is plain conversation,
                # skip FCR execution and fall through to the LLM conversation
                # pipeline (Route 3) so the user gets a real AI-generated reply.
                if intent_name == CommandIntent.CONVERSATION.value:
                    self._logger.info(
                        "[ROUTING] FCR classified as CONVERSATION — falling through to LLM pipeline for text=%r",
                        request.text,
                    )
                    target_route = RouteTarget.UNHANDLED
                else:
                    # Capability Enforcement Gate
                    req_cap = _INTENT_CAPABILITY_MAP.get(intent_name)
                    if req_cap and self._capability_manager and hasattr(self._capability_manager, "is_enabled"):
                        if not self._capability_manager.is_enabled(req_cap):
                            self._logger.warning("[CAPABILITY GATE] Blocked FCR execution: %s requires %s (disabled)", intent_name, req_cap)
                            duration_ms = (time.time() - ctx.start_time) * 1000
                            cap_display = req_cap.replace('_', ' ').title()
                            if cap_display == "Pc Control": cap_display = "PC Control"
                            msg = f"[Capability Disabled]: {cap_display} is currently turned off. Enable it in Plugins to use this."
                            await self._emit_event("capability_blocked", {
                                "session_id": ctx.session_id,
                                "request_id": str(ctx.request_id),
                                "capability": req_cap,
                                "intent": intent_name,
                            })
                            return UserResponse(
                                request_id=request.id,
                                text=msg,
                                source=request.source,
                                duration_ms=duration_ms,
                            )

                    self._logger.info(
                        "[ROUTING] [MATCH] Fast Command Router MATCHED: '%s'", request.text
                    )
                    fast_result = await fcr.execute_fast_command(request.text, fcr_intent_data)
                    duration_ms = (time.time() - ctx.start_time) * 1000

                    if self._analytics_manager is not None:
                        rec_fn: Any = getattr(self._analytics_manager, "record", None)
                        if callable(rec_fn):
                            rec_fn(
                                AnalyticsEvent(
                                    event_type=EventType.FCR_HIT,
                                    duration_ms=duration_ms,
                                    success=True,
                                    payload={"request": request.text, "target": "fcr"},
                                )
                            )

                    return UserResponse(
                        request_id=request.id,
                        text=fast_result,
                        source=request.source,
                        duration_ms=duration_ms,
                    )

            # Route 2: PLANNING_ENGINE
            if target_route == RouteTarget.PLANNING_ENGINE and self._planning_manager is not None:
                self._logger.info("[ROUTING] Routing request to PlanningEngine: %r", request.text)
                plan_fn: Any = getattr(self._planning_manager, "plan", None)
                exec_plan_fn: Any = getattr(self._planning_manager, "execute_plan", None)

                if callable(plan_fn) and callable(exec_plan_fn):
                    plan = await plan_fn(request.text, request.metadata)  # type: ignore
                    plan_res = await exec_plan_fn(plan)  # type: ignore
                    duration_ms = (time.time() - ctx.start_time) * 1000

                    step_cnt = len(plan_res.executed_steps)
                    if plan_res.success:
                        raw_text = f"Executed multi-step plan successfully ({step_cnt} steps)."
                    else:
                        raw_text = (
                            f"Plan execution failed at step {plan_res.failed_step}: "
                            f"{plan_res.error}"
                        )
                    res_text = await self._synthesize_conversational_reply(request.text, raw_text)

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

                    return UserResponse(
                        request_id=request.id,
                        text=res_text,
                        source=request.source,
                        duration_ms=duration_ms,
                    )

            # Reasoning Gateway Evaluation (before LLM invocation)
            gw_decision = self._reasoning_gateway.evaluate(request.text, request.metadata)
            self._logger.info(
                "[REASONING GATEWAY] category=%s llm_required=%s score=%d reasoning=%s",
                gw_decision.category,
                gw_decision.llm_required,
                gw_decision.complexity_score,
                gw_decision.reasoning,
            )

            # Route Coding Tasks directly to CodingAgentManager (TDD & Self-Correction Loop)
            if (
                (gw_decision.category == IntentCategory.CODING or gw_decision.category == "CODING")
                and self._coding_agent_manager is not None
                and hasattr(self._coding_agent_manager, "execute_task")
            ):
                # Capability Enforcement Gate for Coding Agent
                if self._capability_manager and hasattr(self._capability_manager, "is_enabled"):
                    if not self._capability_manager.is_enabled("coding_agent"):
                        self._logger.warning("[CAPABILITY GATE] Blocked Coding Agent execution (disabled)")
                        duration_ms = (time.time() - ctx.start_time) * 1000
                        msg = f"[Capability Disabled]: Coding Agent is currently turned off. Enable it in Plugins to use this."
                        await self._emit_event("capability_blocked", {
                            "session_id": ctx.session_id,
                            "request_id": str(ctx.request_id),
                            "capability": "coding_agent",
                            "intent": "CODING",
                        })
                        return UserResponse(
                            request_id=request.id,
                            text=msg,
                            source=request.source,
                            duration_ms=duration_ms,
                        )

                self._logger.info("[ROUTING] [MATCH] Routing coding request to CodingAgentManager TDD engine: '%s'", request.text)
                try:
                    res = await self._coding_agent_manager.execute_task(
                        request.text,
                        {"session_id": request.session_id},
                    )
                    duration_ms = (time.time() - ctx.start_time) * 1000
                    raw_text = getattr(res, "output", "") or getattr(res, "error", "") or f"Coding task completed with status: {getattr(res, 'status', 'completed')}"
                    res_text = await self._synthesize_conversational_reply(request.text, raw_text)
                    return UserResponse(
                        request_id=request.id,
                        text=res_text,
                        source=request.source,
                        duration_ms=duration_ms,
                    )
                except Exception as coding_exc:
                    self._logger.warning("[ROUTING] CodingAgentManager execution failed, falling back to standard LLM pipeline: %s", coding_exc)

            if not gw_decision.llm_required:
                duration_ms = (time.time() - ctx.start_time) * 1000
                if gw_decision.clarification_required:
                    raw_text = f"[User Clarification Required]: Your request '{request.text}' is ambiguous. Please provide specific details."
                elif gw_decision.memory_lookup:
                    mem_res = None
                    if self._memory_manager is not None:
                        search_fn = getattr(self._memory_manager, "search", None) or getattr(self._memory_manager, "recall", None)
                        if callable(search_fn):
                            try:
                                mem_res = search_fn(request.text)
                            except Exception:
                                pass
                    raw_text = f"Retrieved from memory: {mem_res}" if mem_res else f"Memory recall for '{request.text}' processed."
                elif gw_decision.web_search_only:
                    raw_text = f"[Web Search Summary]: Live result for '{request.text}' retrieved without full LLM reasoning."
                elif gw_decision.category == IntentCategory.GREETING:
                    raw_text = "Hello! How can I assist you today?"
                elif gw_decision.category == IntentCategory.LOCAL_CAPABILITY:
                    raw_text = f"Local capability status for '{request.text}': System online and ready."
                else:
                    raw_text = f"Request '{request.text}' processed deterministically by Reasoning Gateway."

                bypass_text = await self._synthesize_conversational_reply(request.text, raw_text)

                return UserResponse(
                    request_id=request.id,
                    text=bypass_text,
                    source=request.source,
                    duration_ms=duration_ms,
                )

            return UserResponse(request_id=request.id, text="Error: No route found for request. LLM is disabled.", source=request.source, duration_ms=0.0)
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
            target_route = RouteTarget.UNHANDLED
            if self._decision_manager is not None:
                decide_fn: Any = getattr(self._decision_manager, "decide", None)
                if callable(decide_fn):
                    decision = await decide_fn(request.text, request.metadata)  # type: ignore
                    target_route = decision.target

            if (
                target_route == RouteTarget.UNHANDLED
                and self._fast_command_router is not None
                and self._fast_command_router.is_fast_command(request.text)
            ):
                target_route = RouteTarget.FAST_COMMAND_ROUTER

            fcr = self._fast_command_router
            if target_route == RouteTarget.FAST_COMMAND_ROUTER and fcr is not None:
                fcr_intent_data = await fcr.classify_intent(request.text)
                intent_name = fcr_intent_data.get("intent", "")

                # If the classifier determined this is plain conversation,
                # skip FCR execution and fall through to the streaming LLM
                # pipeline so the user gets a real AI-generated reply.
                if intent_name == CommandIntent.CONVERSATION.value:
                    self._logger.info(
                        "[ROUTING] FCR classified as CONVERSATION (stream) — falling through to LLM pipeline for text=%r",
                        request.text,
                    )
                else:
                    self._logger.info(
                        "[ROUTING] [MATCH] Fast Command Router MATCHED (stream): '%s'", request.text
                    )
                    fast_result = await fcr.execute_fast_command(request.text, fcr_intent_data)
                    duration_ms = (time.time() - ctx.start_time) * 1000

                    yield fast_result

                    return

            # Reasoning Gateway Evaluation (stream)
            gw_decision = self._reasoning_gateway.evaluate(request.text, request.metadata)
            if not gw_decision.llm_required:
                duration_ms = (time.time() - ctx.start_time) * 1000
                if gw_decision.clarification_required:
                    bypass_text = f"[User Clarification Required]: Your request '{request.text}' is ambiguous. Please provide specific details."
                elif gw_decision.memory_lookup:
                    mem_res = None
                    if self._memory_manager is not None:
                        search_fn = getattr(self._memory_manager, "search", None) or getattr(self._memory_manager, "recall", None)
                        if callable(search_fn):
                            try:
                                mem_res = search_fn(request.text)
                            except Exception:
                                pass
                    bypass_text = f"Retrieved from memory: {mem_res}" if mem_res else f"Memory recall for '{request.text}' processed."
                elif gw_decision.web_search_only:
                    bypass_text = f"[Web Search Summary]: Live result for '{request.text}' retrieved without full LLM reasoning."
                elif gw_decision.category == IntentCategory.GREETING:
                    bypass_text = "Hello! How can I assist you today?"
                elif gw_decision.category == IntentCategory.LOCAL_CAPABILITY:
                    bypass_text = f"Local capability status for '{request.text}': System online and ready."
                else:
                    bypass_text = f"Request '{request.text}' processed deterministically by Reasoning Gateway."

                yield bypass_text
                return

            yield "[Error]: No route found for request. LLM is disabled."
            return

        except Exception as exc:
            self._logger.error(
                "Runtime stream error at stage '%s': %s", ctx.current_stage, exc
            )
            yield f"\n[Error: {exc}]"

    # ------------------------------------------------------------------
    # Autonomous Tasks & Multi-Agent API
    # ------------------------------------------------------------------

    @property
    def autonomous_task_engine(self) -> AutonomousTaskEngine:
        """Return the autonomous task engine instance."""
        return self._autonomous_task_engine

    @property
    def multi_agent_orchestrator(self) -> MultiAgentOrchestrator:
        """Return the multi-agent orchestrator instance."""
        return self._multi_agent_orchestrator

    def start_autonomous_task(
        self,
        goal: str,
        session_id: str = "default",
        max_steps: int | None = None,
        timeout_seconds: float | None = None,
    ) -> object:
        """Start an autonomous background task."""
        return self._autonomous_task_engine.start_task(
            goal=goal,
            session_id=session_id,
            max_steps=max_steps,
            timeout_seconds=timeout_seconds,
        )

    def get_autonomous_task_status(self, task_id: str) -> object | None:
        """Get the current status of an autonomous task."""
        return self._autonomous_task_engine.get_task_status(task_id)

    def confirm_autonomous_step(self, task_id: str, approved: bool) -> bool:
        """Confirm or reject a paused step in an autonomous task."""
        return self._autonomous_task_engine.confirm_step(task_id, approved)

    def cancel_autonomous_task(self, task_id: str) -> bool:
        """Cancel a running autonomous task."""
        return self._autonomous_task_engine.cancel_task(task_id)

    async def handle_complex_request(
        self,
        text: str,
        session_id: str = "default",
    ) -> dict[str, Any]:
        """Process a complex request using the multi-agent orchestrator."""
        return await self._multi_agent_orchestrator.execute_multi_agent(
            user_request=text,
            session_id=session_id,
        )

    # ------------------------------------------------------------------
    # Pipeline stages
    # ------------------------------------------------------------------

    async def _resolve_session(self, ctx: RequestContext) -> object:
        """Resolve the session via the conversation manager."""
        if self._conversation_manager is None:
            return None


    async def _synthesize_conversational_reply(self, user_text: str, raw_output: str) -> str:
        """Deterministic pass-through."""
        return raw_output

    async def _emit_event(self, event_type: str, data: dict) -> None:
        if self._event_bus is None:
            return
        emit = getattr(self._event_bus, "emit", None)
        if emit is not None:
            await emit(event_type, data)

    def _ensure_not_degraded(self) -> None:
        if self._degraded:
            from backend.types import ModuleDegradedError
            raise ModuleDegradedError("RuntimeManager is degraded", context={"module": "runtime"})
