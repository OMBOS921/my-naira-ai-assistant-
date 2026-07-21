from __future__ import annotations

import logging
from typing import Any

from backend.modules.security._types import RiskLevel

_LOG = logging.getLogger("naira.security.risk")


_HIGH_RISK_TOOLS: frozenset[str] = frozenset({
    "pc_power",
    "pc_process",
    "shell_exec",
    "registry_write",
    "registry_delete",
    "format_drive",
})

_MEDIUM_RISK_TOOLS: frozenset[str] = frozenset({
    "pc_launch_application",
    "pc_keyboard",
    "pc_clipboard",
    "pc_volume",
    "browser_navigate",
    "browser_extract",
})

_DANGEROUS_ARGUMENTS: dict[str, frozenset[str]] = {
    "pc_filesystem": frozenset({"delete_file", "delete_directory"}),
    "pc_process": frozenset({"kill"}),
    "pc_power": frozenset({"shutdown", "restart", "sleep", "hibernate", "lock"}),
    "pc_keyboard": frozenset({"type_text", "press_key", "hotkey"}),
    "pc_clipboard": frozenset({"set_text", "clear"}),
}


class RiskAnalyzer:
    def __init__(
        self,
        max_risk: str = "critical",
        logger: logging.Logger | None = None,
    ) -> None:
        self._max_risk = RiskLevel(max_risk)
        self._logger = logger or _LOG

    def analyze(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> RiskLevel:
        if arguments and tool_name in _DANGEROUS_ARGUMENTS:
            action = str(arguments.get("action", ""))
            if action in _DANGEROUS_ARGUMENTS[tool_name]:
                return RiskLevel.HIGH

        if tool_name in _HIGH_RISK_TOOLS:
            return RiskLevel.HIGH

        if tool_name in _MEDIUM_RISK_TOOLS:
            return RiskLevel.MEDIUM

        return RiskLevel.LOW

    def is_above_threshold(self, risk: RiskLevel) -> bool:
        levels = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        return levels.index(risk) > levels.index(self._max_risk)
