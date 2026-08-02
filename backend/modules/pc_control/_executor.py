"""PCControlExecutor — async execution layer with timeout and error isolation.

Wraps port/adapter operations so that ``PCControlManager`` never deals
with raw exceptions or hanging calls.
"""

from __future__ import annotations

import asyncio
import logging

from backend.modules.pc_control._exceptions import PCControlNotImplementedError
from backend.modules.pc_control.ports.pc_control_port import PCControlPort
from backend.types import ToolResult

_LOG = logging.getLogger("naira.pc_control.executor")


_PLACEHOLDER_MESSAGE = "PC control adapter not configured — no OS automation driver available"


class PCControlExecutor:
    """Safe execution wrapper for PC-control operations.

    Parameters
    ----------
    adapter : PCControlPort
        The active PC-control adapter (placeholder or real).
    default_timeout : float
        Default timeout for all operations.
    logger : logging.Logger | None
        Module-scoped logger.
    """

    def __init__(
        self,
        adapter: PCControlPort,
        default_timeout: float = 30.0,
        logger: logging.Logger | None = None,
    ) -> None:
        self._adapter = adapter
        self._default_timeout = default_timeout
        self._logger = logger or _LOG

    async def execute(
        self,
        action: str,
        **kwargs: object,
    ) -> ToolResult:
        """Execute a PC-control action with timeout and error isolation.

        Parameters
        ----------
        action : str
            The action to execute (maps to a method on the adapter).
        **kwargs : object
            Arguments forwarded to the adapter method.

        Returns
        -------
        ToolResult
            Result of the operation (never raises).
        """
        effective_timeout = float(kwargs.pop("timeout", self._default_timeout))
        method = getattr(self._adapter, action, None)
        if method is None:
            return ToolResult(
                status="error",
                error=f"Unknown PC-control action: {action}",
            )

        try:
            result = await asyncio.wait_for(
                method(**kwargs),
                timeout=effective_timeout + 1.0,
            )
            if result is None:
                return ToolResult(status="success", output=f"Action '{action}' completed")
            if hasattr(result, "success") and not getattr(result, "success"):
                err_msg = getattr(result, "error", None) or f"Action '{action}' failed"
                return ToolResult(status="error", error=str(err_msg))
            return ToolResult(status="success", output=str(result))
        except PCControlNotImplementedError:
            return ToolResult(
                status="error",
                error=_PLACEHOLDER_MESSAGE,
            )
        except asyncio.TimeoutError:
            return ToolResult(
                status="timeout",
                error=f"Action '{action}' timed out after {effective_timeout}s",
            )
        except Exception as exc:
            self._logger.warning("Action '%s' failed: %s", action, exc)
            return ToolResult(
                status="error",
                error=f"Action '{action}' failed: {exc}",
            )

    async def mouse_get_position(self) -> ToolResult:
        return await self.execute("mouse_get_position")

    async def mouse_move_to(self, x: int, y: int, duration: float = 0.0) -> ToolResult:
        return await self.execute("mouse_move_to", x=x, y=y, duration=duration)

    async def mouse_click(self, x: int | None = None, y: int | None = None) -> ToolResult:
        return await self.execute("mouse_click", x=x, y=y)

    async def mouse_double_click(self, x: int | None = None, y: int | None = None) -> ToolResult:
        return await self.execute("mouse_double_click", x=x, y=y)

    async def mouse_right_click(self, x: int | None = None, y: int | None = None) -> ToolResult:
        return await self.execute("mouse_right_click", x=x, y=y)

    async def mouse_drag(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration: float = 0.5,
    ) -> ToolResult:
        return await self.execute(
            "mouse_drag",
            start_x=start_x,
            start_y=start_y,
            end_x=end_x,
            end_y=end_y,
            duration=duration,
        )

    async def mouse_scroll(
        self, clicks: int, x: int | None = None, y: int | None = None
    ) -> ToolResult:
        return await self.execute("mouse_scroll", clicks=clicks, x=x, y=y)

    async def keyboard_type_text(self, text: str, interval: float = 0.0) -> ToolResult:
        return await self.execute("keyboard_type_text", text=text, interval=interval)

    async def keyboard_press_key(self, key: str) -> ToolResult:
        return await self.execute("keyboard_press_key", key=key)

    async def keyboard_hotkey(self, *keys: str) -> ToolResult:
        effective_timeout = self._default_timeout
        try:
            result = await asyncio.wait_for(
                self._adapter.keyboard_hotkey(*keys),
                timeout=effective_timeout + 1.0,
            )
            if result is None:
                return ToolResult(status="success", output="Hotkey completed")
            return ToolResult(status="success", output=str(result))
        except PCControlNotImplementedError:
            return ToolResult(
                status="error",
                error=_PLACEHOLDER_MESSAGE,
            )
        except asyncio.TimeoutError:
            return ToolResult(
                status="timeout",
                error=f"Hotkey timed out after {effective_timeout}s",
            )
        except Exception as exc:
            self._logger.warning("Hotkey failed: %s", exc)
            return ToolResult(
                status="error",
                error=f"Hotkey failed: {exc}",
            )

    async def clipboard_get_text(self) -> ToolResult:
        return await self.execute("clipboard_get_text")

    async def clipboard_set_text(self, text: str) -> ToolResult:
        return await self.execute("clipboard_set_text", text=text)

    async def clipboard_clear(self) -> ToolResult:
        return await self.execute("clipboard_clear")

    async def filesystem_list_directory(self, path: str) -> ToolResult:
        return await self.execute("filesystem_list_directory", path=path)

    async def filesystem_read_file(self, path: str, encoding: str = "utf-8") -> ToolResult:
        return await self.execute("filesystem_read_file", path=path, encoding=encoding)

    async def filesystem_write_file(
        self, path: str, content: str, encoding: str = "utf-8"
    ) -> ToolResult:
        return await self.execute(
            "filesystem_write_file", path=path, content=content, encoding=encoding
        )

    async def filesystem_delete_file(self, path: str) -> ToolResult:
        return await self.execute("filesystem_delete_file", path=path)

    async def filesystem_create_directory(self, path: str) -> ToolResult:
        return await self.execute("filesystem_create_directory", path=path)

    async def filesystem_delete_directory(self, path: str, recursive: bool = False) -> ToolResult:
        return await self.execute("filesystem_delete_directory", path=path, recursive=recursive)

    async def window_list(self) -> ToolResult:
        return await self.execute("window_list")

    async def window_get_active(self) -> ToolResult:
        return await self.execute("window_get_active")

    async def window_focus(self, handle: int) -> ToolResult:
        return await self.execute("window_focus", handle=handle)

    async def window_minimize(self, handle: int) -> ToolResult:
        return await self.execute("window_minimize", handle=handle)

    async def window_maximize(self, handle: int) -> ToolResult:
        return await self.execute("window_maximize", handle=handle)

    async def window_close(self, handle: int) -> ToolResult:
        return await self.execute("window_close", handle=handle)

    async def window_resize(self, handle: int, width: int, height: int) -> ToolResult:
        return await self.execute("window_resize", handle=handle, width=width, height=height)

    async def window_move(self, handle: int, x: int, y: int) -> ToolResult:
        return await self.execute("window_move", handle=handle, x=x, y=y)

    async def process_list(self) -> ToolResult:
        return await self.execute("process_list")

    async def process_kill(self, pid: int, force: bool = False) -> ToolResult:
        return await self.execute("process_kill", pid=pid, force=force)

    async def launch_application(
        self,
        app_path: str,
        args: tuple[str, ...] = (),
        working_dir: str | None = None,
    ) -> ToolResult:
        return await self.execute(
            "launch_application",
            app_path=app_path,
            args=args,
            working_dir=working_dir,
        )

    async def notification_show(
        self, title: str, message: str, duration: float = 5.0
    ) -> ToolResult:
        return await self.execute(
            "notification_show", title=title, message=message, duration=duration
        )

    async def power_shutdown(self) -> ToolResult:
        return await self.execute("power_shutdown")

    async def power_restart(self) -> ToolResult:
        return await self.execute("power_restart")

    async def power_sleep(self) -> ToolResult:
        return await self.execute("power_sleep")

    async def power_hibernate(self) -> ToolResult:
        return await self.execute("power_hibernate")

    async def power_lock(self) -> ToolResult:
        return await self.execute("power_lock")

    async def volume_get(self) -> ToolResult:
        return await self.execute("volume_get")

    async def volume_set(self, level: float) -> ToolResult:
        return await self.execute("volume_set", level=level)

    async def volume_mute(self, muted: bool) -> ToolResult:
        return await self.execute("volume_mute", muted=muted)

    async def screen_get_size(self) -> ToolResult:
        return await self.execute("screen_get_size")

    async def screen_capture(
        self,
        region: tuple[int, int, int, int] | None = None,
        save_path: str | None = None,
    ) -> ToolResult:
        return await self.execute("screen_capture", region=region, save_path=save_path)

    async def screen_list_displays(self) -> ToolResult:
        return await self.execute("screen_list_displays")

    async def filesystem_zip_directory(self, source_dir: str, output_zip_path: str) -> ToolResult:
        return await self.execute("filesystem_zip_directory", source_dir=source_dir, output_zip_path=output_zip_path)

    async def filesystem_extract_archive(self, zip_path: str, extract_to_dir: str) -> ToolResult:
        return await self.execute("filesystem_extract_archive", zip_path=zip_path, extract_to_dir=extract_to_dir)

    async def filesystem_copy_item(self, source_path: str, dest_path: str) -> ToolResult:
        return await self.execute("filesystem_copy_item", source_path=source_path, dest_path=dest_path)

    async def filesystem_move_item(self, source_path: str, dest_path: str) -> ToolResult:
        return await self.execute("filesystem_move_item", source_path=source_path, dest_path=dest_path)

    async def get_system_metrics(self) -> ToolResult:
        return await self.execute("get_system_metrics")

    async def get_open_ports(self) -> ToolResult:
        return await self.execute("get_open_ports")

    # ── System Settings / Software / Accounts ───────────────────────────

    async def wifi_set_power(self, enabled: bool) -> ToolResult:
        return await self.execute("wifi_set_power", enabled=enabled)

    async def wifi_get_power(self) -> ToolResult:
        return await self.execute("wifi_get_power")

    async def wifi_list_networks(self) -> ToolResult:
        return await self.execute("wifi_list_networks")

    async def wifi_connect(self, ssid: str, password: str | None = None) -> ToolResult:
        return await self.execute("wifi_connect", ssid=ssid, password=password)

    async def bluetooth_set_power(self, enabled: bool) -> ToolResult:
        return await self.execute("bluetooth_set_power", enabled=enabled)

    async def bluetooth_get_power(self) -> ToolResult:
        return await self.execute("bluetooth_get_power")

    async def bluetooth_list_devices(self) -> ToolResult:
        return await self.execute("bluetooth_list_devices")

    async def bluetooth_pair(self, device_address: str, pin: str | None = None) -> ToolResult:
        return await self.execute("bluetooth_pair", device_address=device_address, pin=pin)

    async def display_get_brightness(self) -> ToolResult:
        return await self.execute("display_get_brightness")

    async def display_set_brightness(self, level: int) -> ToolResult:
        return await self.execute("display_set_brightness", level=level)

    async def display_get_resolution(self) -> ToolResult:
        return await self.execute("display_get_resolution")

    async def display_set_resolution(self, width: int, height: int) -> ToolResult:
        return await self.execute("display_set_resolution", width=width, height=height)

    async def display_list_resolutions(self) -> ToolResult:
        return await self.execute("display_list_resolutions")

    async def display_set_night_light(self, enabled: bool) -> ToolResult:
        return await self.execute("display_set_night_light", enabled=enabled)

    async def display_get_night_light(self) -> ToolResult:
        return await self.execute("display_get_night_light")

    async def display_set_dark_mode(self, enabled: bool) -> ToolResult:
        return await self.execute("display_set_dark_mode", enabled=enabled)

    async def display_get_dark_mode(self) -> ToolResult:
        return await self.execute("display_get_dark_mode")

    async def power_set_airplane_mode(self, enabled: bool) -> ToolResult:
        return await self.execute("power_set_airplane_mode", enabled=enabled)

    async def power_get_airplane_mode(self) -> ToolResult:
        return await self.execute("power_get_airplane_mode")

    async def power_set_do_not_disturb(self, enabled: bool) -> ToolResult:
        return await self.execute("power_set_do_not_disturb", enabled=enabled)

    async def power_get_do_not_disturb(self) -> ToolResult:
        return await self.execute("power_get_do_not_disturb")

    async def software_list_installed(self) -> ToolResult:
        return await self.execute("software_list_installed")

    async def software_install(self, package: str) -> ToolResult:
        return await self.execute("software_install", package=package)

    async def software_uninstall(self, package: str) -> ToolResult:
        return await self.execute("software_uninstall", package=package)

    async def software_check_update(self, package: str) -> ToolResult:
        return await self.execute("software_check_update", package=package)

    async def account_list_users(self) -> ToolResult:
        return await self.execute("account_list_users")

    async def account_get_current_user(self) -> ToolResult:
        return await self.execute("account_get_current_user")

    async def account_create_user(self, username: str, password: str | None = None) -> ToolResult:
        return await self.execute("account_create_user", username=username, password=password)

    async def account_set_enabled(self, username: str, enabled: bool) -> ToolResult:
        return await self.execute("account_set_enabled", username=username, enabled=enabled)

    async def account_modify_groups(
        self,
        username: str,
        add: list[str] | None = None,
        remove: list[str] | None = None,
    ) -> ToolResult:
        return await self.execute(
            "account_modify_groups", username=username, add=add, remove=remove
        )

    @property
    def is_available(self) -> bool:
        return self._adapter.is_available
