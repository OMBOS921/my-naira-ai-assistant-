from __future__ import annotations

import fnmatch
import logging

from backend.modules.security._types import PermissionMode, RiskLevel, SecurityPolicyRule

_LOG = logging.getLogger("naira.security.policy")


class SecurityPolicyEngine:
    def __init__(
        self,
        default_policy: str = "allow",
        logger: logging.Logger | None = None,
    ) -> None:
        self._default_policy = PermissionMode(default_policy)
        self._rules: list[SecurityPolicyRule] = []
        self._logger = logger or _LOG

    def add_rule(self, rule: SecurityPolicyRule) -> None:
        self._rules.append(rule)
        self._logger.info(
            "Policy rule added: %s -> %s (risk=%s, approval=%s)",
            rule.tool_pattern,
            rule.mode.value,
            rule.risk_level.value,
            rule.require_approval,
        )

    def remove_rule(self, tool_pattern: str) -> int:
        before = len(self._rules)
        self._rules = [r for r in self._rules if r.tool_pattern != tool_pattern]
        return before - len(self._rules)

    def clear(self) -> None:
        self._rules.clear()

    def evaluate(
        self,
        tool_name: str,
        risk_level: RiskLevel = RiskLevel.LOW,
    ) -> PermissionMode:
        matching = [r for r in self._rules if fnmatch.fnmatch(tool_name, r.tool_pattern)]
        matching.sort(key=lambda r: r.risk_level.value, reverse=True)

        for rule in matching:
            if risk_level.value <= rule.risk_level.value:
                self._logger.debug(
                    "Policy matched: %s -> %s (rule: %s)",
                    tool_name,
                    rule.mode.value,
                    rule.tool_pattern,
                )
                return rule.mode

        return self._default_policy

    def requires_approval(
        self,
        tool_name: str,
        risk_level: RiskLevel = RiskLevel.LOW,
    ) -> bool:
        matching = [r for r in self._rules if fnmatch.fnmatch(tool_name, r.tool_pattern)]
        return any(r.require_approval for r in matching)

    def list_rules(self) -> list[SecurityPolicyRule]:
        return list(self._rules)
