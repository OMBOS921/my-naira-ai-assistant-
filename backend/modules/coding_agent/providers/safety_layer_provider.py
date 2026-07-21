from __future__ import annotations

import logging

from backend.modules.coding_agent.ports.safety_layer_port import SafetyLayerPort

_LOG = logging.getLogger("naira.coding_agent.safety")

_BLOCKED_COMMANDS: set[str] = {
    "rm", "del", "rd", "rmdir", "format", "mkfs",
    "dd", "shutdown", "reboot", "halt", "poweroff",
    "init", "killall", "pkill", "taskkill",
}
_BLOCKED_PATHS_PREFIXES: tuple[str, ...] = (
    "/etc", "/usr", "/bin", "/boot", "/dev", "/proc", "/sys",
    "C:\\Windows", "C:\\Program Files", "C:\\ProgramData",
)
_RISKY_COMMANDS: set[str] = {
    "sudo", "su", "chmod", "chown", "passwd", "mount", "umount",
}


class DefaultSafetyLayerProvider(SafetyLayerPort):
    """Default provider for the Safety Layer port.

    Validates commands, file operations, and git operations for safety.
    """

    def __init__(
        self,
        *,
        enabled: bool = True,
        logger: logging.Logger | None = None,
    ) -> None:
        self._logger = logger or _LOG
        self._available: bool = True
        self._enabled = enabled

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def provider_name(self) -> str:
        return "default_safety"

    async def validate_command(
        self,
        command: str,
        args: list[str],
    ) -> tuple[bool, str | None]:
        if not self._enabled:
            return (True, None)
        base = command.lower().split("/")[-1] if "/" in command else command.lower()
        base = base.split("\\")[-1] if "\\" in base else base
        if base in _BLOCKED_COMMANDS:
            return (False, f"Command '{base}' is blocked for safety")
        if base in _RISKY_COMMANDS:
            return (False, f"Command '{base}' requires explicit approval")
        for arg in args:
            if arg.startswith("-") and arg in ("-rf", "/s", "/q"):
                return (False, f"Force/recursive flag '{arg}' not allowed")
        return (True, None)

    async def validate_file_operation(
        self,
        operation: str,
        path: str,
    ) -> tuple[bool, str | None]:
        if not self._enabled:
            return (True, None)
        if operation == "delete":
            for prefix in _BLOCKED_PATHS_PREFIXES:
                if path.lower().startswith(prefix.lower()):
                    return (False, f"Cannot delete files in protected path: {prefix}")
        return (True, None)

    async def validate_git_operation(
        self,
        operation: str,
        args: list[str],
    ) -> tuple[bool, str | None]:
        if not self._enabled:
            return (True, None)
        risky_ops = {"push --force", "push -f", "reset --hard", "clean -fd"}
        cmd = f"{operation} {' '.join(args)}"
        for risky in risky_ops:
            if risky in cmd:
                return (False, f"Git operation '{risky}' is blocked for safety")
        return (True, None)

    async def validate_network_access(
        self,
        url: str,
    ) -> tuple[bool, str | None]:
        return (True, None)

    async def close(self) -> None:
        self._available = False
        self._logger.info("Safety layer provider closed")
