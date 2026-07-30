from __future__ import annotations

import shlex

from backend.modules.security._types import RiskLevel, SecurityCheck, SecurityStatus

_COMMAND_DENYLIST: tuple[str, ...] = (
    "rm -rf /",
    "rm -rf ~",
    "rm -rf c:",
    "format",
    "format c:",
    "format d:",
    "del /f /s /q",
    "del /f /s /q c:",
    "rd /s /q",
    "rd /s /q c:",
    "shutdown -s",
    "shutdown -r",
    "shutdown -l",
    "taskkill /f /im",
    "reg delete",
    "reg add",
    "diskpart",
    "bcdedit",
    "mkfs",
)

_COMMAND_ALLOWLIST: tuple[str, ...] = ()

_DANGEROUS_KEYWORDS: tuple[str, ...] = (
    "rm -rf",
    "format",
    "diskpart",
    "bcdedit",
    "reg delete",
    "reg add",
    "shutdown",
    "taskkill",
    "del /f",
    "rd /s",
    "mkfs",
    "dd if=",
    ">nul 2>&1",
    "||",
    "&&",
)


class CommandValidator:
    def __init__(
        self,
        allowlist: tuple[str, ...] | None = None,
        denylist: tuple[str, ...] | None = None,
    ) -> None:
        self._allowlist = allowlist or _COMMAND_ALLOWLIST
        self._denylist = denylist or _COMMAND_DENYLIST

    async def validate(
        self,
        command: str,
    ) -> SecurityCheck:
        for blocked in self._denylist:
            if blocked.lower() in command.lower():
                return SecurityCheck(
                    status=SecurityStatus.DENY,
                    risk_level=RiskLevel.CRITICAL,
                    reason=f"Command matches denylist pattern: '{blocked}'",
                    denied=True,
                )

        for keyword in _DANGEROUS_KEYWORDS:
            if keyword.lower() in command.lower():
                return SecurityCheck(
                    status=SecurityStatus.CONFIRM,
                    risk_level=RiskLevel.HIGH,
                    reason=f"Command contains dangerous keyword: '{keyword}'",
                    requires_confirmation=True,
                )

        return SecurityCheck(status=SecurityStatus.PASS, risk_level=RiskLevel.LOW)

    @staticmethod
    def tokenize(command: str) -> list[str]:
        try:
            return shlex.split(command)
        except ValueError:
            return command.split()
