"""
Runtime — end-to-end AI execution pipeline.

Orchestrates context assembly, prompt compilation, LLM generation with
tool calling, streaming, memory persistence, and event emission.
"""

from __future__ import annotations

from backend.runtime._runtime_manager import RuntimeManager
from backend.runtime._tool_calling_engine import ToolCallingEngine, ToolCallingResult
from backend.runtime.context_router import ContextRouter
from backend.runtime.message_dispatcher import MessageDispatcher
from backend.runtime.request_pipeline import RequestContextResult, RequestPipeline
from backend.runtime.response_pipeline import GenerationResult, ResponsePipeline
from backend.runtime.runtime import Runtime
from backend.runtime.session_manager import SessionManager
from backend.runtime.interaction_manager import (
    InteractionEvent,
    InteractionManager,
    InteractionPhase,
    PersonalityMode,
)

__all__ = [
    "ContextRouter",
    "GenerationResult",
    "InteractionEvent",
    "InteractionManager",
    "InteractionPhase",
    "MessageDispatcher",
    "PersonalityMode",
    "RequestContextResult",
    "RequestPipeline",
    "ResponsePipeline",
    "Runtime",
    "RuntimeManager",
    "SessionManager",
    "ToolCallingEngine",
    "ToolCallingResult",
    "ToolRouter",
]
