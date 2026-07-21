from __future__ import annotations

import os
from pathlib import Path

from backend.modules.security._types import RiskLevel, SecurityCheck, SecurityStatus

_SYSTEM_PATHS: tuple[str, ...] = (
    "C:\\Windows",
    "C:\\Windows\\System32",
    "C:\\Windows\\System",
    "C:\\Program Files",
    "C:\\Program Files (x86)",
    "C:\\ProgramData",
    "/etc",
    "/usr",
    "/bin",
    "/boot",
    "/dev",
    "/proc",
    "/sys",
)

_SENSITIVE_EXTENSIONS: tuple[str, ...] = (
    ".exe", ".dll", ".sys", ".drv", ".vxd",
    ".pif", ".scr", ".com", ".bat", ".cmd",
    ".vbs", ".js", ".ps1", ".sh",
)


class PathValidator:
    def __init__(
        self,
        allowed_paths: tuple[str, ...] = (),
        blocked_paths: tuple[str, ...] = (),
    ) -> None:
        self._allowed_paths = allowed_paths
        self._blocked_paths = blocked_paths

    async def validate(
        self,
        path: str,
    ) -> SecurityCheck:
        resolved = os.path.realpath(path)

        for blocked in self._blocked_paths:
            if self._is_subpath(resolved, os.path.realpath(blocked)):
                return SecurityCheck(
                    status=SecurityStatus.DENY,
                    risk_level=RiskLevel.CRITICAL,
                    reason=f"Path is blocked by policy: '{blocked}'",
                    denied=True,
                )

        if ".." in path.split(os.sep):
            return SecurityCheck(
                status=SecurityStatus.DENY,
                risk_level=RiskLevel.HIGH,
                reason="Directory traversal detected",
                denied=True,
            )

        for sys_path in _SYSTEM_PATHS:
            normalized = os.path.normpath(sys_path)
            if self._is_subpath(resolved, normalized) or resolved == normalized:
                return SecurityCheck(
                    status=SecurityStatus.DENY if self._blocked_paths else SecurityStatus.CONFIRM,
                    risk_level=RiskLevel.CRITICAL,
                    reason=f"Path targets system directory: '{sys_path}'",
                    denied=bool(self._blocked_paths),
                    requires_confirmation=not self._blocked_paths,
                )

        ext = os.path.splitext(resolved)[1].lower()
        if ext in _SENSITIVE_EXTENSIONS:
            return SecurityCheck(
                status=SecurityStatus.CONFIRM,
                risk_level=RiskLevel.HIGH,
                reason=f"Path targets sensitive file type: '{ext}'",
                requires_confirmation=True,
            )

        return SecurityCheck(status=SecurityStatus.PASS, risk_level=RiskLevel.LOW)

    @staticmethod
    def _is_subpath(path: str, parent: str) -> bool:
        try:
            Path(path).relative_to(Path(parent))
            return True
        except ValueError:
            return False
