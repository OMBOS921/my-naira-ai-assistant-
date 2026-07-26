"""
RequestPipeline — builds the complete request context for LLM inference.

Orchestrates:
1. Session resolution (via SessionManager)
2. Context assembly (via ContextManager)
3. Prompt compilation (via PromptManager)
4. Tool definition retrieval (via ToolManager)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from backend.modules.context import ContextManager
from backend.modules.prompt import PromptManager
from backend.orchestrator import EventBus
from backend.runtime.context_router import ContextRouter
from backend.runtime.session_manager import SessionManager
from backend.runtime.tool_router import ToolRouter
from backend.types import Message, ToolDef, UserRequest

_LOG = logging.getLogger("naira.runtime.request_pipeline")


@dataclass(frozen=True)
class RequestContextResult:
    """Result of request pipeline processing.

    Attributes
    ----------
    system_prompt : str
        The compiled system prompt.
    messages : list[Message]
        The assembled conversation messages (including current user message).
    tool_defs : list[ToolDef]
        Available tool definitions for the LLM.
    session_id : str
        The resolved session ID.
    request_id : str
        The request ID.
    """

    system_prompt: str
    messages: list[Message]
    tool_defs: list[ToolDef]
    session_id: str
    request_id: str


class RequestPipeline:
    """Processes an inbound UserRequest into a complete LLM-ready context.

    Pipeline stages:
    1. Session resolution — route to or create session
    2. Context assembly — build conversation context with sliding window
    3. Prompt compilation — render system prompt template with variables
    4. Tool discovery — fetch enabled tool definitions

    Parameters
    ----------
    context_manager : ContextManager | None
        ContextManager instance for context assembly.
    prompt_manager : PromptManager | None
        PromptManager instance for prompt compilation.
    session_manager : SessionManager | None
        SessionManager instance for session resolution.
    event_bus : EventBus | None
        EventBus for stage event emission.
    logger : logging.Logger | None
        Module-scoped logger.
    """

    def __init__(
        self,
        *,
        context_manager: ContextManager | None = None,
        prompt_manager: PromptManager | None = None,
        session_manager: SessionManager | None = None,
        tool_router: ToolRouter | None = None,
        security_manager: object | None = None,
        event_bus: EventBus | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._context_manager = context_manager
        self._prompt_manager = prompt_manager
        self._session_manager = session_manager
        self._tool_router = tool_router
        self._security_manager = security_manager
        self._event_bus = event_bus
        self._logger = logger or _LOG
        self._degraded: bool = False
        self._initialized: bool = False

        self._context_router = ContextRouter(
            context_manager=context_manager,
            event_bus=event_bus,
            logger=logger,
        )

    # ------------------------------------------------------------------
    # Module lifecycle
    # ------------------------------------------------------------------

    async def async_init(self) -> None:
        """Initialise the request pipeline."""
        await self._context_router.async_init()
        self._initialized = True
        self._logger.debug("Request pipeline initialised")

    async def async_shutdown(self) -> None:
        """Release resources."""
        await self._context_router.async_shutdown()
        self._degraded = False
        self._initialized = False
        self._logger.debug("Request pipeline shut down")

    def degrade(self) -> None:
        """Mark as degraded."""
        self._degraded = True
        self._context_router.degrade()
        self._logger.warning("Request pipeline marked degraded")

    @property
    def degraded(self) -> bool:
        return self._degraded

    @property
    def initialized(self) -> bool:
        return self._initialized

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def process(self, request: UserRequest) -> RequestContextResult:
        """Process a user request through the full request pipeline.

        Parameters
        ----------
        request : UserRequest
            The inbound request.

        Returns
        -------
        RequestContextResult
            Complete context ready for LLM inference.
        """
        self._ensure_not_degraded()

        # Stage 0: Security validation (BEFORE session, prompt, context, or LLM)
        if self._security_manager is not None and hasattr(self._security_manager, "validate_input"):
            val_res = self._security_manager.validate_input(request.text)
            if val_res.status == "reject":
                from backend.exceptions import InputRejectedError
                raise InputRejectedError(
                    val_res.reason or "Security validation failed.",
                    context={"reason": val_res.reason, "request_id": str(request.id)},
                )

        # Stage 1: Session resolution
        session = await self._resolve_session(request.session_id)
        await self._emit_event("runtime.session_resolved", {
            "session_id": session.session_id,
            "request_id": str(request.id),
        })

        # Stage 2: Prompt compilation (needed before context assembly)
        system_prompt = self._compile_prompt(session.session_id)
        await self._emit_event("runtime.prompt_compiled", {
            "session_id": session.session_id,
            "request_id": str(request.id),
            "prompt_length": len(system_prompt),
        })

        # Stage 3: Context assembly with compiled prompt
        context = self._assemble_context(
            session_id=session.session_id,
            user_text=request.text,
            system_prompt=system_prompt,
        )
        await self._emit_event("runtime.context_assembled", {
            "session_id": session.session_id,
            "request_id": str(request.id),
            "message_count": len(context.messages),
            "token_count": context.token_count,
        })

        # Stage 4: Tool discovery
        tool_defs = self._get_tool_definitions()
        await self._emit_event("runtime.tools_discovered", {
            "session_id": session.session_id,
            "request_id": str(request.id),
            "tool_count": len(tool_defs),
        })

        return RequestContextResult(
            system_prompt=system_prompt,
            messages=context.messages,
            tool_defs=tool_defs,
            session_id=session.session_id,
            request_id=str(request.id),
        )

    # ------------------------------------------------------------------
    # Pipeline stages
    # ------------------------------------------------------------------

    async def _resolve_session(self, session_id: str) -> object:
        """Resolve or create a session via SessionManager."""
        if self._session_manager is None:
            # Fallback: create a simple session object
            return type("SimpleSession", (), {"session_id": session_id})()
        return await self._session_manager.get_or_create_session(session_id)

    def _assemble_context(self, session_id: str, user_text: str, system_prompt: str = "") -> object:
        """Build context via ContextRouter (which uses ContextManager)."""
        if self._context_router is None:
            return _empty_context()
        return self._context_router.build_context(session_id, user_text, system_prompt)

    def _compile_prompt(self, session_id: str) -> str:
        """Compile system prompt via PromptManager."""
        if self._prompt_manager is None:
            return ""
        try:
            return self._prompt_manager.compile()
        except Exception as exc:
            self._logger.warning("Prompt compilation failed: %s", exc)
            return ""

    def _get_tool_definitions(self) -> list[ToolDef]:
        """Fetch tool definitions via ToolRouter."""
        if self._tool_router is None:
            return []
        return self._tool_router.get_tool_defs()

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
                "RequestPipeline is degraded",
                context={"module": "runtime.request_pipeline"},
            )

    # ------------------------------------------------------------------
    # Properties for testing/debugging
    # ------------------------------------------------------------------

    @property
    def context_router(self) -> ContextRouter:
        return self._context_router


def _empty_context() -> object:
    """Return a minimal context-like object for fallback paths."""
    return type("EmptyContext", (), {"messages": [], "system_prompt": "", "token_count": 0})()
