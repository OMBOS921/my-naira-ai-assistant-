"""PCControlManager — the single public class for the PC-control module.

07_Module_Design.md §2 — Module responsibilities.
21_System_Contracts.md §15 — Tool contracts.
21_System_Contracts.md §4.2 — ModuleInterface protocol.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.exceptions import ModuleDegradedError
from backend.modules.pc_control._application_launcher import PCApplicationLauncher
from backend.modules.pc_control._clipboard import PCClipboard
from backend.modules.pc_control._executor import PCControlExecutor
from backend.modules.pc_control._filesystem import PCFilesystem
from backend.modules.pc_control._keyboard import PCKeyboard
from backend.modules.pc_control._local_adapter import LocalPCControlAdapter
from backend.modules.pc_control._mouse import PCMouse
from backend.modules.pc_control._notification import PCNotification
from backend.modules.pc_control._power import PCPower
from backend.modules.pc_control._process_manager import PCProcessManager
from backend.modules.pc_control._screen import PCScreen
from backend.modules.pc_control._volume import PCVolume
from backend.modules.pc_control._window_manager import PCWindowManager
from backend.modules.pc_control.ports.pc_control_port import PCControlPort
from backend.types import ToolResult

_LOG = logging.getLogger("naira.pc_control")


class PCControlManager:
    """Central PC-control manager — OS automation operations.

    Conforms to ``ModuleInterface`` (``backend/types.py``).

    Parameters
    ----------
    config : object | None
        Application configuration (``AppConfig`` or compatible).
    logger : logging.Logger | None
        Module-scoped logger.
    event_bus : object | None
        ``EventBus`` instance for event emission.
    capability_manager : object | None
        ``CapabilityManager`` instance for capability registration.
    tool_manager : object | None
        ``ToolManager`` instance for tool registration.
    adapter : PCControlPort | None
        PC-control adapter to use.  Defaults to ``LocalPCControlAdapter``
        (placeholder mode).
    default_timeout : float
        Default timeout for PC-control operations (default 30.0).
    """

    def __init__(
        self,
        *,
        config: object | None = None,
        logger: logging.Logger | None = None,
        event_bus: object | None = None,
        capability_manager: object | None = None,
        tool_manager: object | None = None,
        adapter: PCControlPort | None = None,
        default_timeout: float = 30.0,
    ) -> None:
        self._config = config
        self._logger = logger or _LOG
        self._event_bus = event_bus
        self._capability_manager = capability_manager
        self._tool_manager = tool_manager
        self._degraded: bool = False
        self._default_timeout = default_timeout

        # Internal components
        self._adapter = adapter or LocalPCControlAdapter(logger=logger)
        self._mouse = PCMouse(port=self._adapter, logger=logger)
        self._keyboard = PCKeyboard(port=self._adapter, logger=logger)
        self._clipboard = PCClipboard(port=self._adapter, logger=logger)
        self._filesystem = PCFilesystem(port=self._adapter, logger=logger)
        self._window_manager = PCWindowManager(port=self._adapter, logger=logger)
        self._process_manager = PCProcessManager(port=self._adapter, logger=logger)
        self._application_launcher = PCApplicationLauncher(port=self._adapter, logger=logger)
        self._notification = PCNotification(port=self._adapter, logger=logger)
        self._power = PCPower(port=self._adapter, logger=logger)
        self._volume = PCVolume(port=self._adapter, logger=logger)
        self._screen = PCScreen(port=self._adapter, logger=logger)
        self._executor = PCControlExecutor(
            adapter=self._adapter,
            default_timeout=default_timeout,
            logger=logger,
        )

    # ------------------------------------------------------------------
    # Module lifecycle  (ModuleInterface protocol)
    # ------------------------------------------------------------------

    async def async_init(self) -> None:
        """Initialise the PC-control module.

        Registers the ``pc_control`` capability and system tools for
        all OS automation operations.
        """
        self._register_capability()
        self._register_tools()
        adapter_name = type(self._adapter).__name__
        available = self._executor.is_available
        self._logger.info(
            "PC-control manager initialised — adapter=%s adapter_available=%s",
            adapter_name,
            available,
        )

    async def async_shutdown(self) -> None:
        """Release adapter resources."""
        try:
            await self._adapter.close()
        except Exception as exc:
            self._logger.warning("Error closing PC-control adapter: %s", exc)
        self._degraded = False
        self._logger.info("PC-control manager shut down.")

    def degrade(self) -> None:
        """Mark the module as degraded."""
        self._degraded = True
        self._logger.warning("PC-control manager marked degraded")

    @property
    def degraded(self) -> bool:
        return self._degraded

    # ------------------------------------------------------------------
    # Public API — mouse
    # ------------------------------------------------------------------

    async def mouse_get_position(self) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.mouse_get_position", {})
        return await self._executor.mouse_get_position()

    async def mouse_move_to(self, x: int, y: int, duration: float = 0.0) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.mouse_move_to", {"x": x, "y": y})
        return await self._executor.mouse_move_to(x, y, duration=duration)

    async def mouse_click(self, x: int | None = None, y: int | None = None) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.mouse_click", {"x": x, "y": y})
        return await self._executor.mouse_click(x=x, y=y)

    async def mouse_double_click(self, x: int | None = None, y: int | None = None) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.mouse_double_click", {"x": x, "y": y})
        return await self._executor.mouse_double_click(x=x, y=y)

    async def mouse_right_click(self, x: int | None = None, y: int | None = None) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.mouse_right_click", {"x": x, "y": y})
        return await self._executor.mouse_right_click(x=x, y=y)

    async def mouse_drag(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration: float = 0.5,
    ) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.mouse_drag", {})
        return await self._executor.mouse_drag(start_x, start_y, end_x, end_y, duration=duration)

    async def mouse_scroll(
        self, clicks: int, x: int | None = None, y: int | None = None
    ) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.mouse_scroll", {"clicks": clicks})
        return await self._executor.mouse_scroll(clicks, x=x, y=y)

    # ------------------------------------------------------------------
    # Public API — keyboard
    # ------------------------------------------------------------------

    async def keyboard_type_text(self, text: str, interval: float = 0.0) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.keyboard_type_text", {})
        return await self._executor.keyboard_type_text(text, interval=interval)

    async def keyboard_press_key(self, key: str) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.keyboard_press_key", {"key": key})
        return await self._executor.keyboard_press_key(key)

    async def keyboard_hotkey(self, *keys: str) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.keyboard_hotkey", {"keys": keys})
        return await self._executor.keyboard_hotkey(*keys)

    # ------------------------------------------------------------------
    # Public API — clipboard
    # ------------------------------------------------------------------

    async def clipboard_get_text(self) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.clipboard_get_text", {})
        return await self._executor.clipboard_get_text()

    async def clipboard_set_text(self, text: str) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.clipboard_set_text", {})
        return await self._executor.clipboard_set_text(text)

    async def clipboard_clear(self) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.clipboard_clear", {})
        return await self._executor.clipboard_clear()

    # ------------------------------------------------------------------
    # Public API — filesystem
    # ------------------------------------------------------------------

    async def filesystem_list_directory(self, path: str) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.filesystem_list_directory", {"path": path})
        return await self._executor.filesystem_list_directory(path)

    async def filesystem_read_file(self, path: str, encoding: str = "utf-8") -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.filesystem_read_file", {"path": path})
        return await self._executor.filesystem_read_file(path, encoding=encoding)

    async def filesystem_write_file(
        self, path: str, content: str, encoding: str = "utf-8"
    ) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.filesystem_write_file", {"path": path})
        return await self._executor.filesystem_write_file(path, content, encoding=encoding)

    async def filesystem_delete_file(self, path: str) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.filesystem_delete_file", {"path": path})
        return await self._executor.filesystem_delete_file(path)

    async def filesystem_create_directory(self, path: str) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.filesystem_create_directory", {"path": path})
        return await self._executor.filesystem_create_directory(path)

    async def filesystem_delete_directory(self, path: str, recursive: bool = False) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.filesystem_delete_directory", {"path": path})
        return await self._executor.filesystem_delete_directory(path, recursive=recursive)

    # ------------------------------------------------------------------
    # Public API — windows
    # ------------------------------------------------------------------

    async def window_list(self) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.window_list", {})
        return await self._executor.window_list()

    async def window_get_active(self) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.window_get_active", {})
        return await self._executor.window_get_active()

    async def window_focus(self, handle: int) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.window_focus", {"handle": handle})
        return await self._executor.window_focus(handle)

    async def window_minimize(self, handle: int) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.window_minimize", {"handle": handle})
        return await self._executor.window_minimize(handle)

    async def window_maximize(self, handle: int) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.window_maximize", {"handle": handle})
        return await self._executor.window_maximize(handle)

    async def window_close(self, handle: int) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.window_close", {"handle": handle})
        return await self._executor.window_close(handle)

    async def window_resize(self, handle: int, width: int, height: int) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.window_resize", {"handle": handle})
        return await self._executor.window_resize(handle, width, height)

    async def window_move(self, handle: int, x: int, y: int) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.window_move", {"handle": handle})
        return await self._executor.window_move(handle, x, y)

    # ------------------------------------------------------------------
    # Public API — processes
    # ------------------------------------------------------------------

    async def process_list(self) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.process_list", {})
        return await self._executor.process_list()

    async def process_kill(self, pid: int, force: bool = False) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.process_kill", {"pid": pid})
        return await self._executor.process_kill(pid, force=force)

    async def safe_kill_process(self, pid: int | None = None, name: str | None = None, force: bool = False) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.safe_kill_process", {"pid": pid, "name": name})
        res = await self._process_manager.safe_kill_process(pid=pid, name=name, force=force)
        return ToolResult(status="success", output=res)

    async def filesystem_zip_directory(self, source_dir: str, output_zip_path: str) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.zip_directory", {"source": source_dir, "output": output_zip_path})
        return await self._executor.filesystem_zip_directory(source_dir, output_zip_path)

    async def filesystem_extract_archive(self, zip_path: str, extract_to_dir: str) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.extract_archive", {"zip_path": zip_path, "target": extract_to_dir})
        return await self._executor.filesystem_extract_archive(zip_path, extract_to_dir)

    async def filesystem_copy_item(self, source_path: str, dest_path: str) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.copy_item", {"source": source_path, "dest": dest_path})
        return await self._executor.filesystem_copy_item(source_path, dest_path)

    async def filesystem_move_item(self, source_path: str, dest_path: str) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.move_item", {"source": source_path, "dest": dest_path})
        return await self._executor.filesystem_move_item(source_path, dest_path)

    async def get_system_metrics(self) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.get_system_metrics", {})
        return await self._executor.get_system_metrics()

    async def get_open_ports(self) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.get_open_ports", {})
        return await self._executor.get_open_ports()

    # ------------------------------------------------------------------
    # Public API — application launcher
    # ------------------------------------------------------------------

    async def launch_application(
        self,
        app_path: str,
        args: tuple[str, ...] = (),
        working_dir: str | None = None,
    ) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.launch_application", {"app_path": app_path})
        return await self._executor.launch_application(app_path, args=args, working_dir=working_dir)

    # ------------------------------------------------------------------
    # Public API — notifications
    # ------------------------------------------------------------------

    async def notification_show(
        self, title: str, message: str, duration: float = 5.0
    ) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.notification_show", {"title": title})
        return await self._executor.notification_show(title, message, duration=duration)

    # ------------------------------------------------------------------
    # Public API — power
    # ------------------------------------------------------------------

    async def power_shutdown(self) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.power_shutdown", {})
        return await self._executor.power_shutdown()

    async def power_restart(self) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.power_restart", {})
        return await self._executor.power_restart()

    async def power_sleep(self) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.power_sleep", {})
        return await self._executor.power_sleep()

    async def power_hibernate(self) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.power_hibernate", {})
        return await self._executor.power_hibernate()

    async def power_lock(self) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.power_lock", {})
        return await self._executor.power_lock()

    # ------------------------------------------------------------------
    # Public API — volume
    # ------------------------------------------------------------------

    async def volume_get(self) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.volume_get", {})
        return await self._executor.volume_get()

    async def volume_set(self, level: float) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.volume_set", {"level": level})
        return await self._executor.volume_set(level)

    async def volume_mute(self, muted: bool = True) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.volume_mute", {"muted": muted})
        return await self._executor.volume_mute(muted)

    async def volume_unmute(self) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.volume_mute", {"muted": False})
        return await self._executor.volume_mute(False)

    # ------------------------------------------------------------------
    # Public API — screen
    # ------------------------------------------------------------------

    async def screen_get_size(self) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.screen_get_size", {})
        return await self._executor.screen_get_size()

    async def screen_capture(
        self,
        region: tuple[int, int, int, int] | None = None,
        save_path: str | None = None,
    ) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.screen_capture", {})
        return await self._executor.screen_capture(region=region, save_path=save_path)

    async def screen_list_displays(self) -> ToolResult:
        self._ensure_not_degraded()
        await self._emit_event_async("pc_control.screen_list_displays", {})
        return await self._executor.screen_list_displays()

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def is_available(self) -> bool:
        return self._executor.is_available

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _register_capability(self) -> None:
        if self._capability_manager is not None:
            register_cap = getattr(self._capability_manager, "register", None)
            if register_cap is not None:
                from backend.modules.capability.capability import Capability

                register_cap(Capability(name="pc_control", version="0.1.0"))

    def _register_tools(self) -> None:
        if self._tool_manager is not None:
            register = getattr(self._tool_manager, "register_tool", None)
            if register is not None:
                from backend.modules.tools import ToolDefinition

                tool_defs: list[tuple[str, str, dict[str, object], str]] = [
                    (
                        "pc_mouse",
                        (
                            "Control the mouse cursor — move, click, "
                            "double-click, right-click, drag, scroll"
                        ),
                        {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "enum": [
                                        "get_position", "move_to", "click",
                                        "double_click", "right_click", "drag", "scroll",
                                    ],
                                    "description": "Mouse action to perform",
                                },
                                "x": {"type": "integer", "description": "X coordinate"},
                                "y": {"type": "integer", "description": "Y coordinate"},
                            },
                            "required": ["action"],
                        },
                        "pc_control",
                    ),
                    (
                        "pc_keyboard",
                        "Simulate keyboard input — type text, press keys, send hotkeys",
                        {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "enum": ["type_text", "press_key", "hotkey"],
                                    "description": "Keyboard action to perform",
                                },
                                "text": {"type": "string", "description": "Text to type"},
                                "key": {"type": "string", "description": "Key name to press"},
                                "keys": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Keys for hotkey combination",
                                },
                            },
                            "required": ["action"],
                        },
                        "pc_control",
                    ),
                    (
                        "pc_clipboard",
                        "Read from or write to the system clipboard",
                        {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "enum": ["get_text", "set_text", "clear"],
                                    "description": "Clipboard action to perform",
                                },
                                "text": {
                                    "type": "string",
                                    "description": "Text to set on clipboard",
                                },
                            },
                            "required": ["action"],
                        },
                        "pc_control",
                    ),
                    (
                        "pc_filesystem",
                        "List, read, write, create, edit, open, or delete files and directories",
                        {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "enum": [
                                        "list_directory", "read_file", "write_file",
                                        "delete_file", "create_directory", "delete_directory",
                                        "open_file", "open_folder", "open",
                                    ],
                                    "description": "Filesystem action to perform",
                                },
                                "path": {"type": "string", "description": "File or directory path"},
                                "content": {"type": "string", "description": "Content to write"},
                                "recursive": {
                                    "type": "boolean",
                                    "description": "Delete recursively",
                                },
                            },
                            "required": ["action", "path"],
                        },
                        "pc_control",
                    ),
                    (
                        "pc_window",
                        "List, focus, resize, move, minimise, maximise, or close windows",
                        {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "enum": [
                                        "list", "get_active", "focus", "minimize",
                                        "maximize", "close", "resize", "move",
                                    ],
                                    "description": "Window action to perform",
                                },
                                "handle": {"type": "integer", "description": "Window handle"},
                                "width": {"type": "integer", "description": "New width"},
                                "height": {"type": "integer", "description": "New height"},
                                "x": {"type": "integer", "description": "New X position"},
                                "y": {"type": "integer", "description": "New Y position"},
                            },
                            "required": ["action"],
                        },
                        "pc_control",
                    ),
                    (
                        "pc_process",
                        "List running processes or terminate a process by PID",
                        {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "enum": ["list", "kill"],
                                    "description": "Process action to perform",
                                },
                                "pid": {"type": "integer", "description": "Process ID to kill"},
                                "force": {"type": "boolean", "description": "Force kill"},
                            },
                            "required": ["action"],
                        },
                        "pc_control",
                    ),
                    (
                        "pc_launch_application",
                        "Launch an application by path with optional arguments",
                        {
                            "type": "object",
                            "properties": {
                                "app_path": {"type": "string", "description": "Path to executable"},
                                "args": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Command-line arguments",
                                },
                                "working_dir": {
                                    "type": "string",
                                    "description": "Working directory",
                                },
                            },
                            "required": ["app_path"],
                        },
                        "pc_control",
                    ),
                    (
                        "pc_notification",
                        "Show a desktop notification",
                        {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string", "description": "Notification title"},
                                "message": {"type": "string", "description": "Notification body"},
                                "duration": {
                                    "type": "number",
                                    "description": "Display duration (seconds)",
                                },
                            },
                            "required": ["title", "message"],
                        },
                        "pc_control",
                    ),
                    (
                        "pc_power",
                        "Shut down, restart, sleep, hibernate, or lock the system",
                        {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "enum": ["shutdown", "restart", "sleep", "hibernate", "lock"],
                                    "description": "Power action to perform",
                                },
                            },
                            "required": ["action"],
                        },
                        "pc_control",
                    ),
                    (
                        "pc_volume",
                        "Get or set the system volume level, mute or unmute audio",
                        {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "enum": ["get", "set", "mute", "unmute"],
                                    "description": "Volume action to perform",
                                },
                                "level": {
                                    "type": "number",
                                    "description": "Volume level (0.0 to 1.0)",
                                },
                            },
                            "required": ["action"],
                        },
                        "pc_control",
                    ),
                    (
                        "pc_screen",
                        "Get screen size, capture screenshots, or list displays",
                        {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "enum": ["get_size", "capture", "list_displays"],
                                    "description": "Screen action to perform",
                                },
                                "region": {
                                    "type": "array",
                                    "items": {"type": "integer"},
                                    "description": "Capture region [left, top, width, height]",
                                },
                                "save_path": {
                                    "type": "string",
                                    "description": "Save screenshot to file",
                                },
                            },
                            "required": ["action"],
                        },
                        "pc_control",
                    ),
                    (
                        "mouse_click",
                        "Click mouse at screen coordinates X and Y",
                        {
                            "type": "object",
                            "properties": {
                                "x": {"type": "integer", "description": "X coordinate"},
                                "y": {"type": "integer", "description": "Y coordinate"},
                            },
                            "required": ["x", "y"],
                        },
                        "pc_control",
                    ),
                    (
                        "keyboard_type",
                        "Type text on keyboard into focused window",
                        {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string", "description": "Text to type"},
                            },
                            "required": ["text"],
                        },
                        "pc_control",
                    ),
                    (
                        "window_focus",
                        "Bring window to front and focus by window handle",
                        {
                            "type": "object",
                            "properties": {
                                "handle": {"type": "integer", "description": "Window handle integer"},
                            },
                            "required": ["handle"],
                        },
                        "pc_control",
                    ),
                    (
                        "mouse_move_to",
                        "Move mouse cursor smoothly to screen coordinates X and Y",
                        {
                            "type": "object",
                            "properties": {
                                "x": {"type": "integer", "description": "X coordinate"},
                                "y": {"type": "integer", "description": "Y coordinate"},
                            },
                            "required": ["x", "y"],
                        },
                        "pc_control",
                    ),
                    (
                        "screen_capture",
                        "Capture a screenshot of the active desktop display",
                        {
                            "type": "object",
                            "properties": {},
                        },
                        "pc_control",
                    ),
                ]

                for name, description, parameters, category in tool_defs:
                    register(
                        ToolDefinition(
                            name=name,
                            description=description,
                            parameters=parameters,
                            category=category,
                            timeout_seconds=self._default_timeout,
                        ),
                        self._handle_pc_tool,
                    )

    async def _handle_pc_tool(self, **kwargs: object) -> ToolResult:
        """Generic tool handler for PC-control tools.

        The first keyword argument determines which manager method to call.
        """
        tool_name = str(kwargs.pop("_tool_name", ""))
        action = str(kwargs.get("action", ""))

        if tool_name == "mouse_click":
            x_val = kwargs.get("x")
            y_val = kwargs.get("y")
            return await self.mouse_click(x=int(x_val) if x_val is not None else None, y=int(y_val) if y_val is not None else None)
        elif tool_name == "keyboard_type":
            return await self.keyboard_type_text(str(kwargs.get("text", "")))
        elif tool_name == "window_focus":
            return await self.window_focus(int(kwargs.get("handle", 0)))
        elif tool_name == "mouse_move_to":
            return await self.mouse_move_to(int(kwargs.get("x", 0)), int(kwargs.get("y", 0)))
        elif tool_name == "screen_capture":
            return await self.screen_capture()

        method_map: dict[str, dict[str, str]] = {
            "pc_mouse": {
                "get_position": "mouse_get_position",
                "move_to": "mouse_move_to",
                "click": "mouse_click",
                "double_click": "mouse_double_click",
                "right_click": "mouse_right_click",
                "drag": "mouse_drag",
                "scroll": "mouse_scroll",
            },
            "pc_keyboard": {
                "type_text": "keyboard_type_text",
                "press_key": "keyboard_press_key",
                "hotkey": "keyboard_hotkey",
            },
            "pc_clipboard": {
                "get_text": "clipboard_get_text",
                "set_text": "clipboard_set_text",
                "clear": "clipboard_clear",
            },
            "pc_filesystem": {
                "list_directory": "filesystem_list_directory",
                "read_file": "filesystem_read_file",
                "write_file": "filesystem_write_file",
                "delete_file": "filesystem_delete_file",
                "create_directory": "filesystem_create_directory",
                "delete_directory": "filesystem_delete_directory",
                "open_file": "launch_application",
                "open_folder": "launch_application",
                "open": "launch_application",
            },
            "pc_window": {
                "list": "window_list",
                "get_active": "window_get_active",
                "focus": "window_focus",
                "minimize": "window_minimize",
                "maximize": "window_maximize",
                "close": "window_close",
                "resize": "window_resize",
                "move": "window_move",
            },
            "pc_process": {
                "list": "process_list",
                "kill": "process_kill",
            },
            "pc_launch_application": {
                "launch": "launch_application",
            },
            "pc_notification": {
                "show": "notification_show",
            },
            "pc_power": {
                "shutdown": "power_shutdown",
                "restart": "power_restart",
                "sleep": "power_sleep",
                "hibernate": "power_hibernate",
                "lock": "power_lock",
            },
            "pc_volume": {
                "get": "volume_get",
                "set": "volume_set",
                "mute": "volume_mute",
                "unmute": "volume_unmute",
            },
            "pc_screen": {
                "get_size": "screen_get_size",
                "capture": "screen_capture",
                "list_displays": "screen_list_displays",
            },
        }

        if tool_name == "pc_filesystem" and action in ("open_file", "open_folder", "open"):
            target_path = str(kwargs.get("path", ""))
            return await self.launch_application(target_path)

        tool_actions = method_map.get(tool_name, {})
        method_name = tool_actions.get(action)

        if method_name is None and tool_name == "pc_launch_application":
            method_name = "launch_application"

        if method_name is None:
            return ToolResult(
                status="error",
                error=f"Unknown action '{action}' for tool '{tool_name}'",
            )

        method = getattr(self, method_name, None)
        if method is None:
            return ToolResult(
                status="error",
                error=f"Method '{method_name}' not implemented",
            )

        kwargs.pop("action", None)
        filtered = {k: v for k, v in kwargs.items() if k != "_tool_name"}
        if isinstance(filtered.get("keys"), (list, tuple)):
            return await method(*filtered["keys"])
        if isinstance(filtered.get("args"), (list, tuple)):
            return await method(
                filtered.get("app_path", ""),
                args=tuple(filtered["args"]),
                working_dir=filtered.get("working_dir"),
            )
        return await method(**filtered)

    def _ensure_not_degraded(self) -> None:
        if self._degraded:
            raise ModuleDegradedError(
                "PCControlManager is degraded",
                context={"module": "pc_control"},
            )

    def _emit_event_sync(self, event_type: str, data: dict[str, Any]) -> None:
        if self._event_bus is None:
            return
        emit = getattr(self._event_bus, "emit", None)
        if emit is not None:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(emit(event_type, data))
            except RuntimeError:
                self._logger.debug("No running loop — event not emitted: %s", event_type)

    async def _emit_event_async(self, event_type: str, data: dict[str, Any]) -> None:
        if self._event_bus is None:
            return
        emit = getattr(self._event_bus, "emit", None)
        if emit is not None:
            await emit(event_type, data)
