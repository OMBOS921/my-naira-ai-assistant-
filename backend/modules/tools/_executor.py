"""
ToolExecutor — async tool execution with timeout, retry, and error isolation.

21_System_Contracts.md §15.4 — Safe execution.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Coroutine
from typing import Any

from backend.exceptions import ToolTimeoutError
from backend.modules.tools._definition import RetryPolicy, ToolDefinition
from backend.modules.tools._permissions import ToolPermission
from backend.modules.tools._registry import ToolHandler, ToolRegistry
from backend.modules.tools._validation import ToolValidation
from backend.types import ToolCall, ToolResult

_LOG = logging.getLogger("naira.tools")


class ToolExecutor:
    """Executes tools asynchronously with full lifecycle management.

    Features:
    - Input validation via ``ToolValidation``.
    - Permission gating via ``ToolPermission``.
    - Timeout enforcement via ``asyncio.wait_for``.
    - Retry with exponential backoff.
    - Error isolation — handler exceptions are caught and returned
      as ``ToolResult`` rather than propagated.
    - Concurrency control via optional ``asyncio.Semaphore``.

    Parameters
    ----------
    registry : ToolRegistry
        The registry to resolve tool definitions and handlers.
    validation : ToolValidation
        Input/output validation helper.
    permission : ToolPermission
        Permission gate.
    max_concurrent : int
        Maximum number of concurrently executing tools
        (default 0 = unlimited).
    logger : logging.Logger | None
        Module-scoped logger.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        validation: ToolValidation,
        permission: ToolPermission,
        max_concurrent: int = 0,
        logger: logging.Logger | None = None,
    ) -> None:
        self._registry = registry
        self._validation = validation
        self._permission = permission
        self._logger = logger or _LOG
        self._semaphore: asyncio.Semaphore | None = (
            asyncio.Semaphore(max_concurrent) if max_concurrent > 0 else None
        )

    # ------------------------------------------------------------------
    # Primary execution API
    # ------------------------------------------------------------------

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        """Execute a tool by name with the given *arguments*.

        Full lifecycle:
        1. Lookup definition + handler.
        2. Check enabled.
        3. Check permissions.
        4. Validate input.
        5. Execute with timeout (and optional semaphore).
        6. Validate output.
        7. Return ``ToolResult``.

        Parameters
        ----------
        name : str
            Registered tool name.
        arguments : dict[str, Any]
            Input arguments for the tool.
        context : dict[str, Any] | None
            Optional execution context for permission checking.

        Returns
        -------
        ToolResult
            The execution result (never raises on tool errors).
        """
        # 1 — Lookup
        definition = self._registry.get(name)
        if definition is None:
            return ToolResult(
                status="error",
                error=f"Tool not found: '{name}'",
            )

        handler = self._registry.get_handler(name)
        if handler is None:
            return ToolResult(
                status="error",
                error=f"No handler registered for tool: '{name}'",
            )

        # 2 — Enabled check
        if not definition.enabled:
            return ToolResult(
                status="error",
                error=f"Tool is disabled: '{name}'",
            )

        # 3 — Permission check
        if not self._permission.check(definition, context):
            return ToolResult(
                status="error",
                error=f"Permission denied for tool: '{name}'",
            )

        # 4 — Input validation
        validation_result = self._validation.validate_input(definition, arguments)
        if validation_result.status == "reject":
            return ToolResult(
                status="error",
                error=f"Input validation failed: {validation_result.reason}",
            )

        sanitized_args = (
            self._validation.sanitize(definition, arguments)
            if validation_result.status == "sanitized"
            else arguments
        )

        # 4 — Execute with timeout + retry
        result = await self._execute_with_policy(
            handler=handler,
            definition=definition,
            arguments=sanitized_args,
        )

        # 6 — Output validation
        output_result = self._validation.validate_output(definition, result)
        if output_result.status == "reject":
            self._logger.warning(
                "Output validation failed for tool '%s': %s",
                name,
                output_result.reason,
            )

        return result

    async def execute_tool_call(
        self,
        tool_call: ToolCall,
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        """Execute a ``ToolCall`` (from an LLM response).

        Parameters
        ----------
        tool_call : ToolCall
            The tool invocation from the LLM.
        context : dict[str, Any] | None
            Optional execution context.

        Returns
        -------
        ToolResult
            The execution result.
        """
        return await self.execute(
            name=tool_call.name,
            arguments=tool_call.arguments,
            context=context,
        )

    async def execute_multi(
        self,
        tool_calls: list[ToolCall],
        context: dict[str, Any] | None = None,
    ) -> list[ToolResult]:
        """Execute multiple ``ToolCall`` objects concurrently.

        Each tool call is executed independently; one failure does
        not affect the others.

        Parameters
        ----------
        tool_calls : list[ToolCall]
            Tool invocations from the LLM.
        context : dict[str, Any] | None
            Optional execution context.

        Returns
        -------
        list[ToolResult]
            Results in the same order as *tool_calls*.
        """
        tasks = [
            self.execute_tool_call(tc, context) for tc in tool_calls
        ]
        return await asyncio.gather(*tasks)

    # ------------------------------------------------------------------
    # Internal execution with policy
    # ------------------------------------------------------------------

    async def _execute_with_policy(
        self,
        handler: ToolHandler,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> ToolResult:
        """Execute *handler* with retry and timeout per the definition's policy."""
        policy = definition.retry_policy
        last_error: Exception | None = None

        for attempt in range(policy.max_retries + 1):
            try:
                call_args = dict(arguments)
                try:
                    sig = inspect.signature(handler)
                    has_var_kw = any(
                        p.kind == inspect.Parameter.VAR_KEYWORD
                        for p in sig.parameters.values()
                    )
                    if "_tool_name" in sig.parameters or has_var_kw:
                        call_args["_tool_name"] = definition.name
                    elif not has_var_kw:
                        # Filter to only parameters present in the signature
                        valid_params = set(sig.parameters.keys())
                        call_args = {k: v for k, v in call_args.items() if k in valid_params}
                except (ValueError, TypeError):
                    pass

                async def _runner() -> ToolResult:
                    if inspect.iscoroutinefunction(handler):
                        res = await handler(**call_args)
                    else:
                        res = handler(**call_args)
                        if inspect.isawaitable(res):
                            res = await res

                    if isinstance(res, ToolResult):
                        return res
                    if isinstance(res, dict) and "status" in res:
                        return ToolResult(
                            status=res.get("status", "success"),
                            output=res.get("output") or str(res.get("result", "")),
                            result=res.get("result", res),
                            error=res.get("error"),
                        )
                    return ToolResult(
                        status="success",
                        output=str(res) if res is not None else "",
                        result=res,
                    )

                if self._semaphore is not None:
                    async with self._semaphore:
                        return await self._run_with_timeout(
                            _runner(),
                            definition.timeout_seconds,
                        )
                return await self._run_with_timeout(
                    _runner(),
                    definition.timeout_seconds,
                )

            except ToolTimeoutError:
                self._logger.warning(
                    "Tool '%s' timed out (attempt %d/%d)",
                    definition.name,
                    attempt + 1,
                    policy.max_retries + 1,
                )
                if attempt < policy.max_retries:
                    await self._backoff(attempt, policy)
                    continue
                return ToolResult(
                    status="timeout",
                    error=f"Tool '{definition.name}' timed out after "
                          f"{policy.max_retries + 1} attempt(s)",
                )

            except Exception as exc:
                last_error = exc
                self._logger.warning(
                    "Tool '%s' failed (attempt %d/%d): %s",
                    definition.name,
                    attempt + 1,
                    policy.max_retries + 1,
                    exc,
                )
                if attempt < policy.max_retries:
                    await self._backoff(attempt, policy)
                    continue
                return ToolResult(
                    status="error",
                    error=f"Tool '{definition.name}' failed: {exc}",
                )

        # Should not reach here, but safety net
        return ToolResult(
            status="error",
            error=f"Tool '{definition.name}' failed: {last_error}" if last_error
            else f"Tool '{definition.name}' failed",
        )

    @staticmethod
    async def _run_with_timeout(
        coro: Coroutine[Any, Any, ToolResult],
        timeout: float,
    ) -> ToolResult:
        """Execute a coroutine with a timeout.

        Raises ``ToolTimeoutError`` on timeout.
        """
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError as err:
            raise ToolTimeoutError(
                f"Tool execution timed out after {timeout}s",
                context={"timeout_seconds": timeout},
            ) from err

    @staticmethod
    async def _backoff(attempt: int, policy: RetryPolicy) -> None:
        """Sleep with exponential backoff.

        delay = min(base * multiplier^attempt, max_delay)
        """
        delay = min(
            policy.base_delay * (policy.backoff_multiplier ** attempt),
            policy.max_delay,
        )
        await asyncio.sleep(delay)
