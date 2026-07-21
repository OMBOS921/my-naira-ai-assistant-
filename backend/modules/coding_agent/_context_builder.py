"""ContextBuilder — assembles rich execution context for agent operations."""

from __future__ import annotations

import logging
from typing import Any

_LOG = logging.getLogger("naira.coding_agent.context")


class ContextBuilder:
    """Assembles execution context from multiple sources.

    Parameters
    ----------
    logger : logging.Logger | None
        Module-scoped logger.
    """

    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._logger = logger or _LOG

    def build_context(
        self,
        *,
        task_id: str = "",
        goal: str = "",
        workspace_info: dict[str, Any] | None = None,
        project_info: dict[str, Any] | None = None,
        memory_context: dict[str, Any] | None = None,
        environment: dict[str, Any] | None = None,
        additional: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Assemble a unified context dictionary.

        Parameters
        ----------
        task_id : str
            Current task identifier.
        goal : str
            Current goal description.
        workspace_info : dict | None
            Workspace metadata.
        project_info : dict | None
            Project analysis data.
        memory_context : dict | None
            Retrieved memory entries.
        environment : dict | None
            Environment variables/state.
        additional : dict | None
            Any additional context data.

        Returns
        -------
        dict[str, Any]
            Unified context dictionary.
        """
        context: dict[str, Any] = {
            "task_id": task_id,
            "goal": goal,
        }
        if workspace_info:
            context["workspace"] = workspace_info
        if project_info:
            context["project"] = project_info
        if memory_context:
            context["memory"] = memory_context
        if environment:
            context["environment"] = environment
        if additional:
            context.update(additional)
        return context
