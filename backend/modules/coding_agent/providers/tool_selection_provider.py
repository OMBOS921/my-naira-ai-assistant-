from __future__ import annotations

import logging
from typing import Any

from backend.modules.coding_agent.ports.tool_selection_port import ToolSelectionPort

_LOG = logging.getLogger("naira.coding_agent.tool_selection")


class DefaultToolSelectionProvider(ToolSelectionPort):
    """Default provider for the Tool Selection port.

    Selects and ranks tools based on task descriptions.
    """

    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._logger = logger or _LOG
        self._available: bool = True

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def provider_name(self) -> str:
        return "default_tool_selector"

    async def select_tools(
        self,
        task_description: str,
        available_tools: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        self._logger.debug("Selecting tools for task: %s", task_description[:50])
        if not available_tools:
            return []
        scored = [(tool, self._score_tool(task_description, tool)) for tool in available_tools]
        scored.sort(key=lambda x: x[1], reverse=True)
        threshold = 0.3
        selected = [tool for tool, score in scored if score >= threshold]
        return selected[:5]

    async def rank_tools(
        self,
        task_description: str,
        tools: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        scored = [(tool, self._score_tool(task_description, tool)) for tool in tools]
        scored.sort(key=lambda x: x[1], reverse=True)
        result = []
        for tool, score in scored:
            entry = dict(tool)
            entry["score"] = round(score, 2)
            result.append(entry)
        return result

    def _score_tool(self, task_description: str, tool: dict[str, Any]) -> float:
        name = tool.get("name", "").lower()
        desc = tool.get("description", "").lower()
        task_lower = task_description.lower()
        score = 0.0
        task_words = set(task_lower.split())
        name_words = set(name.replace("_", " ").split())
        desc_words = set(desc.split())
        common_name = task_words & name_words
        common_desc = task_words & desc_words
        score += len(common_name) * 0.3
        score += len(common_desc) * 0.1
        return min(score, 1.0)

    async def close(self) -> None:
        self._available = False
        self._logger.info("Tool selection provider closed")
