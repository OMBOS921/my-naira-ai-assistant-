"""LocalPCControlAdapter — placeholder PC-control adapter.

Returns ``is_available=False`` and raises ``PCControlNotImplementedError``
on every operation.  This adapter is used when no real OS automation
library (pyautogui, psutil, pynput, etc.) has been configured.

When a real adapter is wired in, ``PCControlManager`` will use it
in place of this placeholder with zero code changes.
"""

from __future__ import annotations

import logging

from backend.modules.pc_control._exceptions import PCControlNotImplementedError
from backend.modules.pc_control._types import (
    ApplicationLaunchResult,
    BluetoothDevice,
    ClipboardContent,
    DisplayInfo,
    FileEntry,
    FileOpResult,
    InstalledPackage,
    PackageOpResult,
    Point,
    ProcessInfo,
    ScreenshotResult,
    ScreenSize,
    SystemMetrics,
    UserAccount,
    VolumeInfo,
    WifiNetwork,
    WindowInfo,
)
from backend.modules.pc_control.ports.pc_control_port import PCControlPort

_LOG = logging.getLogger("naira.pc_control.adapter")


class LocalPCControlAdapter(PCControlPort):
    """Placeholder adapter that signals that no real OS automation
    driver is available.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or _LOG

    @property
    def is_available(self) -> bool:
        return False

    # ------------------------------------------------------------------
    # Mouse
    # ------------------------------------------------------------------

    async def mouse_get_position(self) -> Point:
        raise PCControlNotImplementedError(context={"operation": "mouse_get_position"})

    async def mouse_move_to(self, x: int, y: int, duration: float = 0.0) -> None:
        raise PCControlNotImplementedError(context={"operation": "mouse_move_to", "x": x, "y": y})

    async def mouse_click(self, x: int | None = None, y: int | None = None) -> None:
        raise PCControlNotImplementedError(context={"operation": "mouse_click"})

    async def mouse_double_click(self, x: int | None = None, y: int | None = None) -> None:
        raise PCControlNotImplementedError(context={"operation": "mouse_double_click"})

    async def mouse_right_click(self, x: int | None = None, y: int | None = None) -> None:
        raise PCControlNotImplementedError(context={"operation": "mouse_right_click"})

    async def mouse_drag(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration: float = 0.5,
    ) -> None:
        raise PCControlNotImplementedError(context={"operation": "mouse_drag"})

    async def mouse_scroll(self, clicks: int, x: int | None = None, y: int | None = None) -> None:
        raise PCControlNotImplementedError(context={"operation": "mouse_scroll"})

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------

    async def keyboard_type_text(self, text: str, interval: float = 0.0) -> None:
        raise PCControlNotImplementedError(context={"operation": "keyboard_type_text"})

    async def keyboard_press_key(self, key: str) -> None:
        raise PCControlNotImplementedError(context={"operation": "keyboard_press_key", "key": key})

    async def keyboard_hotkey(self, *keys: str) -> None:
        raise PCControlNotImplementedError(context={"operation": "keyboard_hotkey", "keys": keys})

    # ------------------------------------------------------------------
    # Clipboard
    # ------------------------------------------------------------------

    async def clipboard_get_text(self) -> ClipboardContent:
        raise PCControlNotImplementedError(context={"operation": "clipboard_get_text"})

    async def clipboard_set_text(self, text: str) -> None:
        raise PCControlNotImplementedError(context={"operation": "clipboard_set_text"})

    async def clipboard_clear(self) -> None:
        raise PCControlNotImplementedError(context={"operation": "clipboard_clear"})

    # ------------------------------------------------------------------
    # Filesystem
    # ------------------------------------------------------------------

    async def filesystem_list_directory(self, path: str) -> list[FileEntry]:
        raise PCControlNotImplementedError(
            context={"operation": "filesystem_list_directory", "path": path}
        )

    async def filesystem_read_file(self, path: str, encoding: str = "utf-8") -> str:
        raise PCControlNotImplementedError(
            context={"operation": "filesystem_read_file", "path": path}
        )

    async def filesystem_write_file(self, path: str, content: str, encoding: str = "utf-8") -> FileOpResult:
        raise PCControlNotImplementedError(
            context={"operation": "filesystem_write_file", "path": path}
        )

    async def filesystem_delete_file(self, path: str) -> None:
        raise PCControlNotImplementedError(
            context={"operation": "filesystem_delete_file", "path": path}
        )

    async def filesystem_create_directory(self, path: str) -> FileOpResult:
        raise PCControlNotImplementedError(
            context={"operation": "filesystem_create_directory", "path": path}
        )

    async def filesystem_delete_directory(self, path: str, recursive: bool = False) -> None:
        raise PCControlNotImplementedError(
            context={"operation": "filesystem_delete_directory", "path": path}
        )

    # ------------------------------------------------------------------
    # Windows
    # ------------------------------------------------------------------

    async def window_list(self) -> list[WindowInfo]:
        raise PCControlNotImplementedError(context={"operation": "window_list"})

    async def window_get_active(self) -> WindowInfo | None:
        raise PCControlNotImplementedError(context={"operation": "window_get_active"})

    async def window_focus(self, handle: int) -> None:
        raise PCControlNotImplementedError(context={"operation": "window_focus"})

    async def window_minimize(self, handle: int) -> None:
        raise PCControlNotImplementedError(context={"operation": "window_minimize"})

    async def window_maximize(self, handle: int) -> None:
        raise PCControlNotImplementedError(context={"operation": "window_maximize"})

    async def window_close(self, handle: int) -> None:
        raise PCControlNotImplementedError(context={"operation": "window_close"})

    async def window_resize(self, handle: int, width: int, height: int) -> None:
        raise PCControlNotImplementedError(context={"operation": "window_resize"})

    async def window_move(self, handle: int, x: int, y: int) -> None:
        raise PCControlNotImplementedError(context={"operation": "window_move"})

    # ------------------------------------------------------------------
    # Processes
    # ------------------------------------------------------------------

    async def process_list(self) -> list[ProcessInfo]:
        raise PCControlNotImplementedError(context={"operation": "process_list"})

    async def process_kill(self, pid: int, force: bool = False) -> None:
        raise PCControlNotImplementedError(context={"operation": "process_kill"})

    # ------------------------------------------------------------------
    # Application launcher
    # ------------------------------------------------------------------

    async def launch_application(
        self,
        app_path: str,
        args: tuple[str, ...] = (),
        working_dir: str | None = None,
    ) -> ApplicationLaunchResult:
        raise PCControlNotImplementedError(
            context={"operation": "launch_application", "app_path": app_path}
        )

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------

    async def notification_show(
        self,
        title: str,
        message: str,
        duration: float = 5.0,
    ) -> None:
        raise PCControlNotImplementedError(context={"operation": "notification_show"})

    # ------------------------------------------------------------------
    # Power
    # ------------------------------------------------------------------

    async def power_shutdown(self) -> None:
        raise PCControlNotImplementedError(context={"operation": "power_shutdown"})

    async def power_restart(self) -> None:
        raise PCControlNotImplementedError(context={"operation": "power_restart"})

    async def power_sleep(self) -> None:
        raise PCControlNotImplementedError(context={"operation": "power_sleep"})

    async def power_hibernate(self) -> None:
        raise PCControlNotImplementedError(context={"operation": "power_hibernate"})

    async def power_lock(self) -> None:
        raise PCControlNotImplementedError(context={"operation": "power_lock"})

    # ------------------------------------------------------------------
    # Volume
    # ------------------------------------------------------------------

    async def volume_get(self) -> VolumeInfo:
        raise PCControlNotImplementedError(context={"operation": "volume_get"})

    async def volume_set(self, level: float) -> None:
        raise PCControlNotImplementedError(context={"operation": "volume_set"})

    async def volume_mute(self, muted: bool) -> None:
        raise PCControlNotImplementedError(context={"operation": "volume_mute"})

    # ------------------------------------------------------------------
    # Screen
    # ------------------------------------------------------------------

    async def screen_get_size(self) -> ScreenSize:
        raise PCControlNotImplementedError(context={"operation": "screen_get_size"})

    async def screen_capture(
        self,
        region: tuple[int, int, int, int] | None = None,
        save_path: str | None = None,
    ) -> ScreenshotResult:
        raise PCControlNotImplementedError(context={"operation": "screen_capture"})

    async def screen_list_displays(self) -> list[DisplayInfo]:
        raise PCControlNotImplementedError(context={"operation": "screen_list_displays"})

    # ------------------------------------------------------------------
    # Pro-Level Utilities
    # ------------------------------------------------------------------

    async def filesystem_zip_directory(self, source_dir: str, output_zip_path: str) -> FileOpResult:
        raise PCControlNotImplementedError(context={"operation": "filesystem_zip_directory"})

    async def filesystem_extract_archive(self, zip_path: str, extract_to_dir: str) -> FileOpResult:
        raise PCControlNotImplementedError(context={"operation": "filesystem_extract_archive"})

    async def filesystem_copy_item(self, source_path: str, dest_path: str) -> FileOpResult:
        raise PCControlNotImplementedError(context={"operation": "filesystem_copy_item"})

    async def filesystem_move_item(self, source_path: str, dest_path: str) -> FileOpResult:
        raise PCControlNotImplementedError(context={"operation": "filesystem_move_item"})

    async def get_system_metrics(self) -> SystemMetrics:
        raise PCControlNotImplementedError(context={"operation": "get_system_metrics"})

    async def get_open_ports(self) -> list[int]:
        raise PCControlNotImplementedError(context={"operation": "get_open_ports"})

    # ------------------------------------------------------------------
    # System Settings / Software / Accounts
    # ------------------------------------------------------------------

    async def wifi_set_power(self, enabled: bool) -> None:
        raise PCControlNotImplementedError(
            context={"operation": "wifi_set_power", "enabled": enabled}
        )

    async def wifi_get_power(self) -> bool:
        raise PCControlNotImplementedError(context={"operation": "wifi_get_power"})

    async def wifi_list_networks(self) -> list[WifiNetwork]:
        raise PCControlNotImplementedError(context={"operation": "wifi_list_networks"})

    async def wifi_connect(self, ssid: str, password: str | None = None) -> None:
        raise PCControlNotImplementedError(
            context={"operation": "wifi_connect", "ssid": ssid}
        )

    async def bluetooth_set_power(self, enabled: bool) -> None:
        raise PCControlNotImplementedError(
            context={"operation": "bluetooth_set_power", "enabled": enabled}
        )

    async def bluetooth_get_power(self) -> bool:
        raise PCControlNotImplementedError(context={"operation": "bluetooth_get_power"})

    async def bluetooth_list_devices(self) -> list[BluetoothDevice]:
        raise PCControlNotImplementedError(
            context={"operation": "bluetooth_list_devices"}
        )

    async def bluetooth_pair(self, device_address: str, pin: str | None = None) -> None:
        raise PCControlNotImplementedError(
            context={"operation": "bluetooth_pair", "device_address": device_address}
        )

    async def display_get_brightness(self) -> int:
        raise PCControlNotImplementedError(
            context={"operation": "display_get_brightness"}
        )

    async def display_set_brightness(self, level: int) -> None:
        raise PCControlNotImplementedError(
            context={"operation": "display_set_brightness", "level": level}
        )

    async def display_get_resolution(self) -> tuple[int, int]:
        raise PCControlNotImplementedError(
            context={"operation": "display_get_resolution"}
        )

    async def display_set_resolution(self, width: int, height: int) -> None:
        raise PCControlNotImplementedError(
            context={"operation": "display_set_resolution"}
        )

    async def display_list_resolutions(self) -> list[tuple[int, int]]:
        raise PCControlNotImplementedError(
            context={"operation": "display_list_resolutions"}
        )

    async def display_set_night_light(self, enabled: bool) -> None:
        raise PCControlNotImplementedError(
            context={"operation": "display_set_night_light", "enabled": enabled}
        )

    async def display_get_night_light(self) -> bool:
        raise PCControlNotImplementedError(
            context={"operation": "display_get_night_light"}
        )

    async def display_set_dark_mode(self, enabled: bool) -> None:
        raise PCControlNotImplementedError(
            context={"operation": "display_set_dark_mode", "enabled": enabled}
        )

    async def display_get_dark_mode(self) -> bool:
        raise PCControlNotImplementedError(
            context={"operation": "display_get_dark_mode"}
        )

    async def power_set_airplane_mode(self, enabled: bool) -> None:
        raise PCControlNotImplementedError(
            context={"operation": "power_set_airplane_mode", "enabled": enabled}
        )

    async def power_get_airplane_mode(self) -> bool:
        raise PCControlNotImplementedError(
            context={"operation": "power_get_airplane_mode"}
        )

    async def power_set_do_not_disturb(self, enabled: bool) -> None:
        raise PCControlNotImplementedError(
            context={"operation": "power_set_do_not_disturb", "enabled": enabled}
        )

    async def power_get_do_not_disturb(self) -> bool:
        raise PCControlNotImplementedError(
            context={"operation": "power_get_do_not_disturb"}
        )

    async def software_list_installed(self) -> list[InstalledPackage]:
        raise PCControlNotImplementedError(
            context={"operation": "software_list_installed"}
        )

    async def software_install(self, package: str) -> PackageOpResult:
        raise PCControlNotImplementedError(
            context={"operation": "software_install", "package": package}
        )

    async def software_uninstall(self, package: str) -> PackageOpResult:
        raise PCControlNotImplementedError(
            context={"operation": "software_uninstall", "package": package}
        )

    async def software_check_update(self, package: str) -> bool:
        raise PCControlNotImplementedError(
            context={"operation": "software_check_update", "package": package}
        )

    async def account_list_users(self) -> list[UserAccount]:
        raise PCControlNotImplementedError(context={"operation": "account_list_users"})

    async def account_get_current_user(self) -> UserAccount:
        raise PCControlNotImplementedError(
            context={"operation": "account_get_current_user"}
        )

    async def account_create_user(self, username: str, password: str | None = None) -> UserAccount:
        raise PCControlNotImplementedError(
            context={"operation": "account_create_user", "username": username}
        )

    async def account_set_enabled(self, username: str, enabled: bool) -> None:
        raise PCControlNotImplementedError(
            context={"operation": "account_set_enabled", "username": username}
        )

    async def account_modify_groups(
        self,
        username: str,
        add: list[str] | None = None,
        remove: list[str] | None = None,
    ) -> None:
        raise PCControlNotImplementedError(
            context={"operation": "account_modify_groups", "username": username}
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        self._logger.debug("LocalPCControlAdapter.close() — no-op")
