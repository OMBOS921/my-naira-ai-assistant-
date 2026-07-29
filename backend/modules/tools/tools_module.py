"""
ToolManager — the single public class for the tools module.

07_Module_Design.md §2 — Module responsibilities.
21_System_Contracts.md §15 — Tool contracts.
21_System_Contracts.md §4.2 — ModuleInterface protocol.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.exceptions import ModuleDegradedError
from backend.modules.tools._definition import ToolDefinition
from backend.modules.tools._executor import ToolExecutor
from backend.modules.tools._permissions import ToolPermission
from backend.modules.tools._registry import ToolHandler, ToolRegistry
from backend.modules.tools._validation import ToolValidation
from backend.types import ToolCall, ToolDef, ToolResult

_LOG = logging.getLogger("naira.tools")


class ToolManager:
    """Central tool manager — registration, discovery, and execution.

    Conforms to ``ModuleInterface`` (``backend/types.py``).

    Parameters
    ----------
    config : object | None
        Application configuration (``AppConfig`` or compatible).
    logger : logging.Logger | None
        Module-scoped logger.  If ``None``, a default logger is used.
    event_bus : object | None
        ``EventBus`` instance for event emission.
    capability_manager : object | None
        ``CapabilityManager`` instance for capability registration.
    permission_checker : object | None
        Permission checker for tool permission gating.
    max_concurrent : int
        Maximum concurrent tool executions (default 10).
    default_timeout : float
        Default timeout for tool execution (default 30.0).
    """

    def __init__(
        self,
        *,
        config: object | None = None,
        logger: logging.Logger | None = None,
        event_bus: object | None = None,
        capability_manager: object | None = None,
        permission_checker: object | None = None,
        security_manager: object | None = None,
        max_concurrent: int = 10,
        default_timeout: float = 30.0,
    ) -> None:
        self._config = config
        self._logger = logger or _LOG
        self._event_bus = event_bus
        self._capability_manager = capability_manager
        self._security_manager = security_manager
        self._degraded: bool = False

        self._default_timeout = default_timeout
        self._max_concurrent = max_concurrent

        # Internal components
        self._registry = ToolRegistry(logger=logger)
        self._validation = ToolValidation()
        self._permission = ToolPermission(
            permission_checker=permission_checker,
            logger=logger,
        )
        self._executor = ToolExecutor(
            registry=self._registry,
            validation=self._validation,
            permission=self._permission,
            max_concurrent=max_concurrent,
            logger=logger,
        )

    # ------------------------------------------------------------------
    # Module lifecycle  (ModuleInterface protocol)
    # ------------------------------------------------------------------

    async def async_init(self) -> None:
        """Initialise the tool manager.

        Registers built-in system tools if a capability manager is
        configured.
        """
        self._register_system_tools()
        self._logger.info(
            "Tool manager initialised — %d tool(s), %d categor(ies)",
            self._registry.tool_count,
            len(self._registry.categories),
        )

    async def async_shutdown(self) -> None:
        """Release all tool registrations."""
        self._registry.clear()
        self._degraded = False
        self._logger.info("Tool manager shut down.")

    def degrade(self) -> None:
        """Mark the module as degraded and clear registrations."""
        self._registry.clear()
        self._degraded = True
        self._logger.warning("Tool manager marked degraded")

    @property
    def degraded(self) -> bool:
        return self._degraded

    # ------------------------------------------------------------------
    # Registration API
    # ------------------------------------------------------------------

    def register_tool(
        self,
        definition: ToolDefinition,
        handler: ToolHandler,
    ) -> None:
        """Register a tool with its definition and async handler.

        Parameters
        ----------
        definition : ToolDefinition
            The tool descriptor.
        handler : ToolHandler
            Async callable that executes the tool.

        Raises
        ------
        ValueError
            If a tool with the same name is already registered.
        ModuleDegradedError
            If the manager is degraded.
        """
        self._ensure_not_degraded()
        self._registry.register(definition, handler)
        self._emit_event_sync("tool.registered", {
            "name": definition.name,
            "category": definition.category,
        })

    def unregister_tool(self, name: str) -> None:
        """Unregister a tool by name."""
        self._ensure_not_degraded()
        self._registry.unregister(name)
        self._emit_event_sync("tool.unregistered", {"name": name})

    # ------------------------------------------------------------------
    # Discovery API
    # ------------------------------------------------------------------

    def get_tool(self, name: str) -> ToolDefinition | None:
        """Retrieve a tool definition by name.

        Returns ``None`` if not found.
        """
        return self._registry.get(name)

    def list_tools(
        self,
        category: str | None = None,
        enabled_only: bool = True,
    ) -> list[ToolDefinition]:
        """List registered tool definitions, optionally filtered."""
        return self._registry.list(category=category, enabled_only=enabled_only)

    def get_categories(self) -> list[str]:
        """Return sorted list of all known tool categories."""
        return self._registry.categories

    def set_security_manager(self, security_manager: object) -> None:
        """Set the security manager after construction.

        Required because ToolManager must be initialised before
        SecurityManager (tools register with ToolManager), but
        ToolManager also needs SecurityManager for execution gating.
        """
        self._security_manager = security_manager

    @property
    def tool_count(self) -> int:
        """Return the total number of registered tools."""
        return self._registry.tool_count

    def has_tool(self, name: str) -> bool:
        """Return ``True`` if a tool with *name* is registered."""
        return self._registry.has(name)

    # ------------------------------------------------------------------
    # Enable / Disable API
    # ------------------------------------------------------------------

    def enable_tool(self, name: str) -> bool:
        """Enable a tool by name.

        Returns ``True`` if the tool was found.
        """
        self._ensure_not_degraded()
        result = self._registry.enable(name)
        if result:
            self._emit_event_sync("tool.enabled", {"name": name})
        return result

    def disable_tool(self, name: str) -> bool:
        """Disable a tool by name.

        Returns ``True`` if the tool was found.
        """
        self._ensure_not_degraded()
        result = self._registry.disable(name)
        if result:
            self._emit_event_sync("tool.disabled", {"name": name})
        return result

    def is_enabled(self, name: str) -> bool:
        """Return ``True`` if the tool exists and is enabled."""
        return self._registry.is_enabled(name)

    # ------------------------------------------------------------------
    # Execution API
    # ------------------------------------------------------------------

    async def execute_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        """Execute a tool by name.

        Parameters
        ----------
        name : str
            Registered tool name.
        arguments : dict[str, Any]
            Input arguments.
        context : dict[str, Any] | None
            Optional execution context for permission checks.

        Returns
        -------
        ToolResult
            The execution result.

        Raises
        ------
        ModuleDegradedError
            If the manager is degraded.
        """
        self._ensure_not_degraded()
        await self._emit_event_async("tool.execution_start", {
            "name": name,
        })

        if self._security_manager is not None:
            check_security = getattr(self._security_manager, "check_tool_execution", None)
            if check_security is not None:
                check = await check_security(name, arguments)
                if getattr(check, "denied", False):
                    result = ToolResult(
                        status="error",
                        error=f"Security denied: {getattr(check, 'reason', 'Not permitted')}",
                    )
                    await self._emit_event_async("tool.execution_complete", {
                        "name": name,
                        "status": result.status,
                    })
                    return result

        result = await self._executor.execute(name, arguments, context)
        await self._emit_event_async("tool.execution_complete", {
            "name": name,
            "status": result.status,
        })
        return result

    async def execute_tool_call(
        self,
        tool_call: ToolCall,
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        """Execute a ``ToolCall`` (from an LLM response)."""
        self._ensure_not_degraded()
        script_code = (
            tool_call.arguments.get("script_code")
            or tool_call.arguments.get("code")
            or ""
        ) if isinstance(tool_call.arguments, dict) else ""

        if tool_call.name == "execute_local_python" or script_code:
            display_text = f"### 🛠️ Executing Tool: `{tool_call.name}`\n```python\n{script_code}\n```"
        else:
            args_str = ", ".join(f"{k}={v!r}" for k, v in tool_call.arguments.items()) if isinstance(tool_call.arguments, dict) and tool_call.arguments else ""
            display_text = f"### 🛠️ Executing Tool: `{tool_call.name}({args_str})`"

        session_id = context.get("session_id", "default") if isinstance(context, dict) else "default"

        await self._emit_event_async("tool_execution_start", {
            "session_id": session_id,
            "tool": tool_call.name,
            "name": tool_call.name,
            "tool_call_id": tool_call.id,
            "arguments": tool_call.arguments,
            "script_code": script_code,
            "text": display_text,
        })

        result = await self._executor.execute_tool_call(tool_call, context)

        content = result.output or result.error or ""
        stdout = result.output or ""
        stderr = result.error or ""
        output_display = f"### 📤 Execution Output:\n```text\n{content}\n```"

        await self._emit_event_async("tool_execution_result", {
            "session_id": session_id,
            "tool": tool_call.name,
            "name": tool_call.name,
            "tool_call_id": tool_call.id,
            "status": result.status,
            "output": content,
            "stdout": stdout,
            "stderr": stderr,
            "text": output_display,
        })

        return result

    async def execute_multi(
        self,
        tool_calls: list[ToolCall],
        context: dict[str, Any] | None = None,
    ) -> list[ToolResult]:
        """Execute multiple ``ToolCall`` objects concurrently."""
        self._ensure_not_degraded()
        return await self._executor.execute_multi(tool_calls, context)

    # ------------------------------------------------------------------
    # Tool definitions for LLM consumption
    # ------------------------------------------------------------------

    def get_tool_defs(
        self,
        category: str | None = None,
    ) -> list[ToolDef]:
        """Return a list of ``ToolDef`` objects for the LLM layer.

        Only enabled tools are included.
        """
        self._ensure_not_degraded()
        definitions = self._registry.list(
            category=category,
            enabled_only=True,
        )
        return [d.to_tool_def() for d in definitions]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _register_system_tools(self) -> None:
        """Register built-in system tools.

        Override or extend this method to add default tools.
        Currently a placeholder — no system tools are pre-registered.
        """
        if self._capability_manager is not None:
            register_cap = getattr(self._capability_manager, "register", None)
            if register_cap is not None:
                from backend.modules.capability.capability import Capability

                register_cap(Capability(name="tools", version="0.1.0"))

    def _ensure_not_degraded(self) -> None:
        if self._degraded:
            raise ModuleDegradedError(
                "ToolManager is degraded",
                context={"module": "tools"},
            )

    def _emit_event_sync(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit an event from a synchronous context.

        Schedules the emit coroutine on the running event loop if
        one is available.
        """
        if self._event_bus is None:
            return
        emit = getattr(self._event_bus, "emit", None)
        if emit is not None:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(emit(event_type, data))
            except RuntimeError:
                self._logger.debug("No running loop — event not emitted: %s", event_type)

    async def _emit_event_async(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit an event from an async context."""
        if self._event_bus is None:
            return
        emit = getattr(self._event_bus, "emit", None)
        if emit is not None:
            await emit(event_type, data)
