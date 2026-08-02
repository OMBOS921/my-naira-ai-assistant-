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
    "wifi_get_power",
    "wifi_list_networks",
    "bluetooth_get_power",
    "bluetooth_list_devices",
    "display_get_brightness",
    "display_get_resolution",
    "display_list_resolutions",
    "display_get_night_light",
    "display_get_dark_mode",
    "power_get_airplane_mode",
    "power_get_do_not_disturb",
    "software_list_installed",
    "software_check_update",
    "account_list_users",
    "account_get_current_user",
    "browser_screenshot",
    "browser_new_tab",
    "browser_close_tab",
    "browser_list_tabs",
    "browser_switch_tab",
    "browser_back",
    "browser_forward",
    "browser_reload",
    "browser_get_cookies",
    "browser_press_key",
    "browser_wait_for_selector",
    "browser_select_option",
    "browser_hover",
    "browser_right_click",
    "browser_drag_and_drop",
    "browser_check",
    "browser_uncheck",
    "browser_export_pdf",
    "browser_get_local_storage",
    "browser_get_session_storage",
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
    "wifi_set_power",
    "wifi_connect",
    "bluetooth_set_power",
    "bluetooth_pair",
    "display_set_brightness",
    "display_set_resolution",
    "display_set_night_light",
    "display_set_dark_mode",
    "power_set_airplane_mode",
    "power_set_do_not_disturb",
    "software_install",
    "software_uninstall",
    "browser_execute_js",
    "browser_download_file",
    "browser_set_cookies",
    "browser_clear_cookies",
    "browser_set_local_storage",
    "browser_clear_local_storage",
    "browser_set_session_storage",
    "browser_clear_session_storage",
    "browser_upload_file",
    "account_create_user",
    "account_set_enabled",
    "account_modify_groups",
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
