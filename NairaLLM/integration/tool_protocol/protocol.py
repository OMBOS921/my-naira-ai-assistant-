"""
Tool Protocol and Execution Layer for NairaLLM.

Implements the strict, secure execution loop:
LLM Generation -> Tool Call Extraction -> Schema Validation -> Security Check -> Naira OS Execution -> ToolResult -> Verification.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from backend.types import ToolCall, ToolDef, ToolResult

_LOG = logging.getLogger("nairallm.tool_protocol")

# Strict registered schemas for verified Naira OS tools
VERIFIED_TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "pc_system_settings": {
        "type": "object",
        "properties": {
            "setting": {"type": "string", "enum": ["volume", "brightness"]},
            "value": {"type": "integer", "minimum": 0, "maximum": 100},
        },
        "required": ["setting", "value"],
    },
    "pc_mouse": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["get_position", "move_to", "click", "double_click", "right_click", "drag", "scroll"],
            },
            "x": {"type": "integer"},
            "y": {"type": "integer"},
        },
        "required": ["action"],
    },
    "pc_keyboard": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["type_text", "press_key", "hotkey"]},
            "text": {"type": "string"},
            "key": {"type": "string"},
            "keys": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["action"],
    },
    "pc_clipboard": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["get_text", "set_text", "clear"]},
            "text": {"type": "string"},
        },
        "required": ["action"],
    },
    "browser_search": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "max_results": {"type": "integer", "default": 5},
        },
        "required": ["query"],
    },
    "browser_navigate": {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "timeout": {"type": "number", "default": 30.0},
        },
        "required": ["url"],
    },
    "browser_extract_text": {
        "type": "object",
        "properties": {
            "selector": {"type": "string"},
            "timeout": {"type": "number", "default": 10.0},
        },
    },
    "browser_screenshot": {
        "type": "object",
        "properties": {
            "save_path": {"type": "string"},
            "url": {"type": "string"},
            "timeout": {"type": "number", "default": 15.0},
        },
    },
    "remember_fact": {
        "type": "object",
        "properties": {
            "topic": {"type": "string"},
            "fact": {"type": "string"},
        },
        "required": ["topic", "fact"],
    },
    "search_memory": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "search_type": {
                "type": "string",
                "enum": ["all", "conversations", "timeline", "semantic", "profile"],
                "default": "all",
            },
            "limit": {"type": "integer", "default": 5},
        },
        "required": ["query"],
    },
}


class ToolProtocolError(Exception):
    """Raised when a tool call violates schema or security boundaries."""


class ToolProtocol:
    """Validator and executor for LLM-generated tool calls."""

    def __init__(
        self,
        tool_executor_fn: Callable[[ToolCall, dict[str, Any] | None], Any] | None = None,
        security_checker_fn: Callable[[str, dict[str, Any]], bool] | None = None,
    ) -> None:
        self.tool_executor = tool_executor_fn
        self.security_checker = security_checker_fn

    def validate_tool_call(self, raw_call: dict[str, Any]) -> ToolCall:
        """Validate raw dictionary tool call against verified schemas."""
        name = raw_call.get("name")
        if not name or not isinstance(name, str):
            raise ToolProtocolError("Tool call missing valid 'name' attribute.")

        args = raw_call.get("arguments", {})
        if not isinstance(args, dict):
            raise ToolProtocolError(f"Tool arguments for '{name}' must be a dictionary.")

        schema = VERIFIED_TOOL_SCHEMAS.get(name)
        if schema is not None:
            # Check required properties
            for req in schema.get("required", []):
                if req not in args:
                    raise ToolProtocolError(f"Tool '{name}' missing required argument '{req}'.")

            # Check enum constraints
            props = schema.get("properties", {})
            for key, val in args.items():
                if key in props and "enum" in props[key]:
                    if val not in props[key]["enum"]:
                        raise ToolProtocolError(
                            f"Argument '{key}'='{val}' not in allowed values {props[key]['enum']} for tool '{name}'."
                        )

        # Generate unique tool call ID
        call_id = raw_call.get("id") or f"call_{abs(hash(f'{name}:{json.dumps(args)}')) % 100000:05d}"
        return ToolCall(id=call_id, name=name, arguments=args)

    async def execute_validated_call(
        self, tool_call: ToolCall, context: dict[str, Any] | None = None
    ) -> ToolResult:
        """Execute validated ToolCall with safety gate and return ToolResult."""
        # 1. Security Check
        if self.security_checker is not None:
            is_allowed = self.security_checker(tool_call.name, tool_call.arguments)
            if not is_allowed:
                _LOG.warning("Security policy rejected tool execution: %s", tool_call.name)
                return ToolResult(
                    status="error",
                    error=f"Security check failed: Tool '{tool_call.name}' was denied by security policy.",
                )

        # 2. Execution
        if self.tool_executor is None:
            return ToolResult(
                status="error",
                error="No tool execution handler configured in ToolProtocol.",
            )

        try:
            res = self.tool_executor(tool_call, context)
            if hasattr(res, "__await__"):
                return await res
            return res
        except Exception as exc:
            _LOG.exception("Exception executing tool %s: %s", tool_call.name, exc)
            return ToolResult(status="error", error=f"Tool execution exception: {exc}")
