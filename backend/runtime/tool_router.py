"""
ToolRouter — routes tool calls to the ToolManager for execution.

Generic tool execution without hardcoded tool knowledge.
All tool discovery and execution goes through ToolManager.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from backend.modules.tools import ToolManager
from backend.orchestrator import EventBus
from backend.types import Message, ToolCall, ToolDef
_LOG = logging.getLogger("naira.runtime.tool_router")


class ToolRouter:
    """Routes tool calls to the ToolManager.

    Never hardcodes tool names or logic.  Delegates all execution
    to the injected ToolManager instance.

    Parameters
    ----------
    tool_manager : ToolManager | None
        ToolManager instance for tool execution.
    llm_manager : Any | None
        LLMManager (optional, for future tool-aware generation).
    event_bus : EventBus | None
        EventBus for event emission.
    logger : logging.Logger | None
        Module-scoped logger.
    """

    def __init__(
        self,
        *,
        tool_manager: ToolManager | None = None,
        llm_manager: object | None = None,
        event_bus: EventBus | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._tool_manager = tool_manager
        self._llm_manager = llm_manager
        self._event_bus = event_bus
        self._logger = logger or _LOG
        self._degraded: bool = False
        self._initialized: bool = False

    # ------------------------------------------------------------------
    # Module lifecycle
    # ------------------------------------------------------------------

    async def async_init(self) -> None:
        """Initialise the tool router."""
        if self._tool_manager is not None:
            init = getattr(self._tool_manager, "async_init", None)
            if init is not None:
                await init()
        self._initialized = True
        self._logger.debug("Tool router initialised")

    async def async_shutdown(self) -> None:
        """Release resources."""
        if self._tool_manager is not None:
            shutdown = getattr(self._tool_manager, "async_shutdown", None)
            if shutdown is not None:
                await shutdown()
        self._degraded = False
        self._initialized = False
        self._logger.debug("Tool router shut down")

    def degrade(self) -> None:
        """Mark as degraded."""
        self._degraded = True
        if self._tool_manager is not None:
            degrade = getattr(self._tool_manager, "degrade", None)
            if degrade is not None:
                degrade()
        self._logger.warning("Tool router marked degraded")

    @property
    def degraded(self) -> bool:
        return self._degraded

    @property
    def initialized(self) -> bool:
        return self._initialized

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute_tool_calls(
        self,
        tool_calls: Sequence[ToolCall],
        session_id: str,
    ) -> list[Message]:
        """Execute a batch of tool calls and return result messages.

        Parameters
        ----------
        tool_calls : Sequence[ToolCall]
            Tool calls to execute.
        session_id : str
            Session identifier for event correlation.

        Returns
        -------
        list[Message]
            Tool result messages (role="tool").
        """
        self._ensure_not_degraded()

        if not tool_calls:
            return []

        if self._tool_manager is None:
            self._logger.warning("No ToolManager available — returning error messages")
            return [
                Message(
                    role="tool",
                    content="Error: tool system unavailable",
                    tool_call_id=tc.id,
                )
                for tc in tool_calls
            ]

        for tc in tool_calls:
            script_code = tc.arguments.get("script_code") or tc.arguments.get("code") or "" if isinstance(tc.arguments, dict) else ""
            if tc.name == "execute_local_python" or script_code:
                display_text = f"### 🛠️ Executing Tool: `{tc.name}`\n```python\n{script_code}\n```"
            else:
                args_str = ", ".join(f"{k}={v!r}" for k, v in tc.arguments.items()) if isinstance(tc.arguments, dict) and tc.arguments else ""
                display_text = f"### 🛠️ Executing Tool: `{tc.name}({args_str})`"

            await self._emit_event("tool_execution_start", {
                "session_id": session_id,
                "tool": tc.name,
                "name": tc.name,
                "tool_call_id": tc.id,
                "arguments": tc.arguments,
                "script_code": script_code,
                "text": display_text,
            })

        await self._emit_event("runtime.tool_execution_start", {
            "session_id": session_id,
            "tool_calls": [{"id": tc.id, "name": tc.name} for tc in tool_calls],
        })

        try:
            results = await self._tool_manager.execute_multi(
                tool_calls=list(tool_calls),
                context={"session_id": session_id},
            )
        except Exception as exc:
            self._logger.error("Tool execution failed: %s", exc)
            await self._emit_event("runtime.tool_execution_error", {
                "session_id": session_id,
                "error": str(exc),
            })
            return [
                Message(
                    role="tool",
                    content=f"Error: {exc}",
                    tool_call_id=tc.id,
                )
                for tc in tool_calls
            ]

        messages: list[Message] = []
        for tc, result in zip(tool_calls, results, strict=True):
            content = result.output or result.error or ""
            stdout = result.output or ""
            stderr = result.error or ""
            display_text = f"### 📤 Execution Output:\n```text\n{content}\n```"

            await self._emit_event("tool_execution_result", {
                "session_id": session_id,
                "tool": tc.name,
                "name": tc.name,
                "tool_call_id": tc.id,
                "status": result.status,
                "output": content,
                "stdout": stdout,
                "stderr": stderr,
                "text": display_text,
            })

            messages.append(
                Message(
                    role="tool",
                    content=content,
                    tool_call_id=tc.id,
                )
            )

        await self._emit_event("runtime.tool_execution_complete", {
            "session_id": session_id,
            "results": [
                {
                    "tool_call_id": tc.id,
                    "name": tc.name,
                    "status": result.status,
                    "output_length": len(result.output or "") if result.output else 0,
                }
                for tc, result in zip(tool_calls, results, strict=True)
            ],
        })

        return messages

    async def execute_single_tool(
        self,
        tool_call: ToolCall,
        session_id: str,
    ) -> Message:
        """Execute a single tool call.

        Convenience method for executing one tool call.

        Parameters
        ----------
        tool_call : ToolCall
            The tool call to execute.
        session_id : str
            Session identifier.

        Returns
        -------
        Message
            Tool result message.
        """
        results = await self.execute_tool_calls([tool_call], session_id)
        return results[0] if results else Message(
            role="tool",
            content="Error: no result returned",
            tool_call_id=tool_call.id,
        )

    # ------------------------------------------------------------------
    # Tool definition access
    # ------------------------------------------------------------------

    def get_tool_defs(self) -> list[ToolDef]:
        """Get all enabled tool definitions for LLM consumption."""
        if self._tool_manager is None:
            return []
        get_defs = getattr(self._tool_manager, "get_tool_defs", None)
        if get_defs is None:
            return []
        return get_defs()

    def has_tool(self, name: str) -> bool:
        """Check if a tool is registered and enabled."""
        if self._tool_manager is None:
            return False
        has_tool = getattr(self._tool_manager, "has_tool", None)
        if has_tool is None:
            return False
        return has_tool(name)

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
                "ToolRouter is degraded",
                context={"module": "runtime.tool_router"},
            )

    # ------------------------------------------------------------------
    # Properties for testing/debugging
    # ------------------------------------------------------------------

    @property
    def tool_manager(self) -> ToolManager | None:
        return self._tool_manager
