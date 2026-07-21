"""
ToolPermission — permission gating for tool execution.

21_System_Contracts.md §15 — Tool contracts.
20_Dependency_Rules.md §2 — Port/Adapter pattern.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.modules.tools._definition import ToolDefinition

_LOG = logging.getLogger("naira.tools")


class ToolPermission:
    """Gates tool execution based on permission requirements.

    Integrates with the capability system's ``PermissionIntegration``
    when available, or operates in a lenient mode that allows all
    executions.

    Parameters
    ----------
    permission_checker : object | None
        An optional permission checker (e.g.
        ``capability.PermissionIntegration``) that provides
        ``check_permission(name, key) -> bool``.
    logger : logging.Logger | None
        Module-scoped logger.
    """

    def __init__(
        self,
        permission_checker: object | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._checker = permission_checker
        self._logger = logger or _LOG

    @property
    def is_lenient(self) -> bool:
        """Return ``True`` if no permission checker is configured
        (all executions are permitted)."""
        return self._checker is None

    def check(
        self,
        definition: ToolDefinition,
        context: dict[str, Any] | None = None,
    ) -> bool:
        """Check whether the tool is permitted to execute.

        In lenient mode (no checker configured), always returns
        ``True``.

        Parameters
        ----------
        definition : ToolDefinition
            The tool descriptor whose permissions to check.
        context : dict[str, Any] | None
            Optional execution context (user ID, session data, etc.).

        Returns
        -------
        bool
            ``True`` if execution is permitted.
        """
        if not definition.required_permissions:
            return True

        if self._checker is None:
            return True

        checker = getattr(self._checker, "check_permission", None)
        if checker is None:
            return True

        for perm in definition.required_permissions:
            if not checker(definition.name, perm):
                self._logger.warning(
                    "Permission denied for tool '%s': required '%s'",
                    definition.name,
                    perm,
                )
                return False

        return True

    def required_permissions(
        self,
        definition: ToolDefinition,
    ) -> list[str]:
        """Return the list of permission keys required by *definition*.

        If a checker is configured, delegates to its
        ``required_permissions`` method for potential enrichment.
        """
        if self._checker is not None:
            rp = getattr(self._checker, "required_permissions", None)
            if rp is not None:
                enriched = rp(definition.name)
                if enriched:
                    return enriched

        return list(definition.required_permissions)
