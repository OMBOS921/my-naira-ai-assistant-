from __future__ import annotations

import logging
from typing import Any

from backend.modules.security._types import RiskLevel, SecurityCheck, SecurityStatus

_LOG = logging.getLogger("naira.security.sandbox")


_SANDBOX_ALLOWED_ACTIONS: tuple[str, ...] = (
    "mouse_get_position",
    "mouse_move_to",
    "mouse_click",
    "mouse_double_click",
    "mouse_right_click",
    "mouse_drag",
    "mouse_scroll",
    "keyboard_type_text",
    "keyboard_press_key",
    "keyboard_hotkey",
    "clipboard_get_text",
    "clipboard_set_text",
    "clipboard_clear",
    "filesystem_list_directory",
    "filesystem_read_file",
    "filesystem_write_file",
    "filesystem_create_directory",
    "window_list",
    "window_get_active",
    "window_focus",
    "window_minimize",
    "window_maximize",
    "window_close",
    "window_resize",
    "window_move",
    "process_list",
    "notification_show",
    "screen_get_size",
    "screen_capture",
    "screen_list_displays",
    "volume_get",
    "volume_set",
    "volume_mute",
    "browser_navigate",
    "browser_search",
    "browser_extract",
)

_SANDBOX_DENIED_ACTIONS: tuple[str, ...] = (
    "filesystem_delete_file",
    "filesystem_delete_directory",
    "process_kill",
    "power_shutdown",
    "power_restart",
    "power_sleep",
    "power_hibernate",
    "power_lock",
    "launch_application",
    "shell_exec",
    "registry_read",
    "registry_write",
    "registry_delete",
)


class SandboxManager:
    def __init__(
        self,
        enabled: bool = True,
        logger: logging.Logger | None = None,
    ) -> None:
        self._enabled = enabled
        self._logger = logger or _LOG

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def check_action(
        self,
        action: str,
        arguments: dict[str, Any] | None = None,
    ) -> SecurityCheck:
        if not self._enabled:
            return SecurityCheck(status=SecurityStatus.PASS, risk_level=RiskLevel.LOW)

        if action in _SANDBOX_DENIED_ACTIONS:
            return SecurityCheck(
                status=SecurityStatus.DENY,
                risk_level=RiskLevel.CRITICAL,
                reason=f"Action '{action}' is denied by sandbox policy",
                denied=True,
            )

        if action in _SANDBOX_ALLOWED_ACTIONS:
            return SecurityCheck(status=SecurityStatus.PASS, risk_level=RiskLevel.LOW)

        return SecurityCheck(
            status=SecurityStatus.CONFIRM,
            risk_level=RiskLevel.MEDIUM,
            reason=f"Action '{action}' is not in sandbox allowlist",
            requires_confirmation=True,
        )

    async def is_path_allowed(self, path: str) -> bool:
        if not self._enabled:
            return True
        lower = path.lower()
        for denied_prefix in ("c:\\windows", "c:\\program files", "c:\\programdata"):
            if lower.startswith(denied_prefix):
                return False
        return True
