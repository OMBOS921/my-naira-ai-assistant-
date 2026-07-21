"""Comprehensive tests for the PC Control module.

Covers:
- Point, ScreenSize, FileEntry, ProcessInfo, WindowInfo, DisplayInfo,
  ClipboardContent, VolumeInfo, ScreenshotResult, ApplicationLaunchResult
  dataclasses
- PCControlNotImplementedError, PCControlError, PCControlTimeoutError,
  PCControlExecutionError, PCControlPermissionError
- LocalPCControlAdapter (is_available=False, all operations raise)
- PCControlExecutor (execute with timeout/error isolation)
- PCControlManager (ModuleInterface lifecycle)
- PCControlPort ABC
- ModuleInterface protocol conformance
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.exceptions import ModuleDegradedError
from backend.modules.pc_control import (
    ApplicationLaunchResult,
    ClipboardContent,
    DisplayInfo,
    FileEntry,
    PCControlManager,
    PCControlPort,
    Point,
    ProcessInfo,
    ScreenshotResult,
    ScreenSize,
    VolumeInfo,
    WindowInfo,
)
from backend.modules.pc_control._exceptions import (
    PCControlError,
    PCControlExecutionError,
    PCControlNotImplementedError,
    PCControlPermissionError,
    PCControlTimeoutError,
)
from backend.modules.pc_control._executor import PCControlExecutor
from backend.modules.pc_control._local_adapter import LocalPCControlAdapter
from backend.types import ModuleInterface

# =========================================================================
# Dataclass tests
# =========================================================================


class TestPoint:
    def test_minimal(self) -> None:
        p = Point(x=10, y=20)
        assert p.x == 10
        assert p.y == 20

    def test_frozen(self) -> None:
        p = Point(x=1, y=2)
        with pytest.raises(AttributeError):
            p.x = 99  # type: ignore[misc]


class TestScreenSize:
    def test_minimal(self) -> None:
        s = ScreenSize(width=1920, height=1080)
        assert s.width == 1920
        assert s.height == 1080

    def test_frozen(self) -> None:
        s = ScreenSize(width=1920, height=1080)
        with pytest.raises(AttributeError):
            s.width = 0  # type: ignore[misc]


class TestFileEntry:
    def test_minimal(self) -> None:
        e = FileEntry(name="test.txt", path="/tmp/test.txt", is_directory=False)
        assert e.name == "test.txt"
        assert e.size_bytes == 0

    def test_directory(self) -> None:
        e = FileEntry(name="folder", path="/tmp/folder", is_directory=True)
        assert e.is_directory is True


class TestProcessInfo:
    def test_minimal(self) -> None:
        p = ProcessInfo(pid=1234, name="python")
        assert p.pid == 1234
        assert p.status == "running"

    def test_frozen(self) -> None:
        p = ProcessInfo(pid=1, name="init")
        with pytest.raises(AttributeError):
            p.pid = 2  # type: ignore[misc]


class TestWindowInfo:
    def test_minimal(self) -> None:
        w = WindowInfo(title="Test", handle=1001)
        assert w.title == "Test"
        assert w.handle == 1001
        assert w.is_visible is True


class TestDisplayInfo:
    def test_minimal(self) -> None:
        d = DisplayInfo(width=1920, height=1080)
        assert d.width == 1920
        assert d.refresh_rate == 60.0


class TestClipboardContent:
    def test_empty(self) -> None:
        c = ClipboardContent()
        assert c.text is None

    def test_with_text(self) -> None:
        c = ClipboardContent(text="hello")
        assert c.text == "hello"


class TestVolumeInfo:
    def test_defaults(self) -> None:
        v = VolumeInfo(level=0.5, muted=False)
        assert v.level == 0.5
        assert v.muted is False


class TestScreenshotResult:
    def test_minimal(self) -> None:
        s = ScreenshotResult(width=800, height=600, data=b"")
        assert s.width == 800
        assert s.path is None


class TestApplicationLaunchResult:
    def test_minimal(self) -> None:
        r = ApplicationLaunchResult(pid=5678, name="notepad")
        assert r.pid == 5678
        assert r.success is True


# =========================================================================
# Exception hierarchy
# =========================================================================


class TestPCControlExceptions:
    def test_pc_control_error_base(self) -> None:
        err = PCControlError("test", context={"module": "pc_control"})
        assert isinstance(err, Exception)
        assert err.context == {"module": "pc_control"}

    def test_pc_control_not_implemented(self) -> None:
        err = PCControlNotImplementedError(context={"operation": "test"})
        assert "not available" in str(err).lower()

    def test_pc_control_timeout(self) -> None:
        err = PCControlTimeoutError("timed out")
        assert isinstance(err, PCControlError)

    def test_pc_control_execution(self) -> None:
        err = PCControlExecutionError("execution failed")
        assert isinstance(err, PCControlError)

    def test_pc_control_permission(self) -> None:
        err = PCControlPermissionError("permission denied")
        assert isinstance(err, PCControlError)


# =========================================================================
# LocalPCControlAdapter
# =========================================================================


class TestLocalPCControlAdapter:
    def test_is_available_false(self) -> None:
        adapter = LocalPCControlAdapter()
        assert adapter.is_available is False

    @pytest.mark.parametrize(
        "method, args",
        [
            ("mouse_get_position", ()),
            ("mouse_move_to", (100, 200)),
            ("mouse_click", ()),
            ("mouse_double_click", ()),
            ("mouse_right_click", ()),
            ("mouse_drag", (0, 0, 100, 100)),
            ("mouse_scroll", (1,)),
            ("keyboard_type_text", ("hello",)),
            ("keyboard_press_key", ("enter",)),
            ("keyboard_hotkey", ("ctrl", "c")),
            ("clipboard_get_text", ()),
            ("clipboard_set_text", ("data",)),
            ("clipboard_clear", ()),
            ("filesystem_list_directory", ("/tmp",)),
            ("filesystem_read_file", ("/tmp/a.txt",)),
            ("filesystem_write_file", ("/tmp/a.txt", "data")),
            ("filesystem_delete_file", ("/tmp/a.txt",)),
            ("filesystem_create_directory", ("/tmp/new",)),
            ("filesystem_delete_directory", ("/tmp",)),
            ("window_list", ()),
            ("window_get_active", ()),
            ("window_focus", (1,)),
            ("window_minimize", (1,)),
            ("window_maximize", (1,)),
            ("window_close", (1,)),
            ("window_resize", (1, 800, 600)),
            ("window_move", (1, 100, 100)),
            ("process_list", ()),
            ("process_kill", (1234,)),
            ("launch_application", ("notepad.exe",)),
            ("notification_show", ("Title", "Message")),
            ("power_shutdown", ()),
            ("power_restart", ()),
            ("power_sleep", ()),
            ("power_hibernate", ()),
            ("power_lock", ()),
            ("volume_get", ()),
            ("volume_set", (0.5,)),
            ("volume_mute", (True,)),
            ("screen_get_size", ()),
            ("screen_capture", ()),
            ("screen_list_displays", ()),
        ],
    )
    @pytest.mark.asyncio
    async def test_all_operations_raise_not_implemented(self, method: str, args: tuple) -> None:
        adapter = LocalPCControlAdapter()
        m = getattr(adapter, method)
        with pytest.raises(PCControlNotImplementedError):
            await m(*args)

    @pytest.mark.asyncio
    async def test_close_is_noop(self) -> None:
        adapter = LocalPCControlAdapter()
        await adapter.close()


# =========================================================================
# PCControlExecutor
# =========================================================================


class _MockPCControlAdapter:
    """Test double that implements PCControlPort with controllable behaviour."""

    def __init__(self, available: bool = True) -> None:
        self._available = available

    @property
    def is_available(self) -> bool:
        return self._available

    async def mouse_get_position(self) -> Point:
        return Point(x=100, y=200)

    async def mouse_move_to(self, x: int, y: int, duration: float = 0.0) -> None:
        return None

    async def mouse_click(self, x: int | None = None, y: int | None = None) -> None:
        return None

    async def mouse_double_click(self, x: int | None = None, y: int | None = None) -> None:
        return None

    async def mouse_right_click(self, x: int | None = None, y: int | None = None) -> None:
        return None

    async def mouse_drag(
        self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5
    ) -> None:
        return None

    async def mouse_scroll(self, clicks: int, x: int | None = None, y: int | None = None) -> None:
        return None

    async def keyboard_type_text(self, text: str, interval: float = 0.0) -> None:
        return None

    async def keyboard_press_key(self, key: str) -> None:
        return None

    async def keyboard_hotkey(self, *keys: str) -> None:
        return None

    async def clipboard_get_text(self) -> ClipboardContent:
        return ClipboardContent(text="mock")

    async def clipboard_set_text(self, text: str) -> None:
        return None

    async def clipboard_clear(self) -> None:
        return None

    async def filesystem_list_directory(self, path: str) -> list[FileEntry]:
        return [FileEntry(name="a.txt", path="/tmp/a.txt", is_directory=False)]

    async def filesystem_read_file(self, path: str, encoding: str = "utf-8") -> str:
        return "file content"

    async def filesystem_write_file(self, path: str, content: str, encoding: str = "utf-8") -> None:
        return None

    async def filesystem_delete_file(self, path: str) -> None:
        return None

    async def filesystem_create_directory(self, path: str) -> None:
        return None

    async def filesystem_delete_directory(self, path: str, recursive: bool = False) -> None:
        return None

    async def window_list(self) -> list[WindowInfo]:
        return [WindowInfo(title="Test", handle=1)]

    async def window_get_active(self) -> WindowInfo | None:
        return WindowInfo(title="Active", handle=2)

    async def window_focus(self, handle: int) -> None:
        return None

    async def window_minimize(self, handle: int) -> None:
        return None

    async def window_maximize(self, handle: int) -> None:
        return None

    async def window_close(self, handle: int) -> None:
        return None

    async def window_resize(self, handle: int, width: int, height: int) -> None:
        return None

    async def window_move(self, handle: int, x: int, y: int) -> None:
        return None

    async def process_list(self) -> list[ProcessInfo]:
        return [ProcessInfo(pid=1, name="init")]

    async def process_kill(self, pid: int, force: bool = False) -> None:
        return None

    async def launch_application(
        self, app_path: str, args: tuple[str, ...] = (), working_dir: str | None = None
    ) -> ApplicationLaunchResult:
        return ApplicationLaunchResult(pid=9999, name="app")

    async def notification_show(self, title: str, message: str, duration: float = 5.0) -> None:
        return None

    async def power_shutdown(self) -> None:
        return None

    async def power_restart(self) -> None:
        return None

    async def power_sleep(self) -> None:
        return None

    async def power_hibernate(self) -> None:
        return None

    async def power_lock(self) -> None:
        return None

    async def volume_get(self) -> VolumeInfo:
        return VolumeInfo(level=0.75, muted=False)

    async def volume_set(self, level: float) -> None:
        return None

    async def volume_mute(self, muted: bool) -> None:
        return None

    async def screen_get_size(self) -> ScreenSize:
        return ScreenSize(width=1920, height=1080)

    async def screen_capture(
        self, region: tuple[int, int, int, int] | None = None, save_path: str | None = None
    ) -> ScreenshotResult:
        return ScreenshotResult(width=1920, height=1080, data=b"pngdata")

    async def screen_list_displays(self) -> list[DisplayInfo]:
        return [DisplayInfo(width=1920, height=1080, is_primary=True)]

    async def close(self) -> None:
        pass


class TestPCControlExecutor:
    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        adapter = _MockPCControlAdapter()
        exe = PCControlExecutor(adapter=adapter)
        result = await exe.execute("mouse_get_position")
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_execute_not_implemented(self) -> None:
        adapter = LocalPCControlAdapter()
        exe = PCControlExecutor(adapter=adapter)
        result = await exe.execute("mouse_get_position")
        assert result.status == "error"
        assert "not configured" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_execute_unknown_action(self) -> None:
        adapter = _MockPCControlAdapter()
        exe = PCControlExecutor(adapter=adapter)
        result = await exe.execute("nonexistent_action")
        assert result.status == "error"
        assert "unknown" in (result.error or "").lower()

    @pytest.mark.asyncio
    async def test_mouse_get_position_success(self) -> None:
        adapter = _MockPCControlAdapter()
        exe = PCControlExecutor(adapter=adapter)
        result = await exe.mouse_get_position()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_mouse_get_position_not_implemented(self) -> None:
        adapter = LocalPCControlAdapter()
        exe = PCControlExecutor(adapter=adapter)
        result = await exe.mouse_get_position()
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_mouse_move_to_success(self) -> None:
        adapter = _MockPCControlAdapter()
        exe = PCControlExecutor(adapter=adapter)
        result = await exe.mouse_move_to(100, 200)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_keyboard_type_text_success(self) -> None:
        adapter = _MockPCControlAdapter()
        exe = PCControlExecutor(adapter=adapter)
        result = await exe.keyboard_type_text("hello")
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_clipboard_get_text_success(self) -> None:
        adapter = _MockPCControlAdapter()
        exe = PCControlExecutor(adapter=adapter)
        result = await exe.clipboard_get_text()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_filesystem_list_directory_success(self) -> None:
        adapter = _MockPCControlAdapter()
        exe = PCControlExecutor(adapter=adapter)
        result = await exe.filesystem_list_directory("/tmp")
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_window_list_success(self) -> None:
        adapter = _MockPCControlAdapter()
        exe = PCControlExecutor(adapter=adapter)
        result = await exe.window_list()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_process_list_success(self) -> None:
        adapter = _MockPCControlAdapter()
        exe = PCControlExecutor(adapter=adapter)
        result = await exe.process_list()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_launch_application_success(self) -> None:
        adapter = _MockPCControlAdapter()
        exe = PCControlExecutor(adapter=adapter)
        result = await exe.launch_application("notepad.exe")
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_notification_show_success(self) -> None:
        adapter = _MockPCControlAdapter()
        exe = PCControlExecutor(adapter=adapter)
        result = await exe.notification_show("Title", "Message")
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_power_shutdown_success(self) -> None:
        adapter = _MockPCControlAdapter()
        exe = PCControlExecutor(adapter=adapter)
        result = await exe.power_shutdown()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_volume_get_success(self) -> None:
        adapter = _MockPCControlAdapter()
        exe = PCControlExecutor(adapter=adapter)
        result = await exe.volume_get()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_screen_get_size_success(self) -> None:
        adapter = _MockPCControlAdapter()
        exe = PCControlExecutor(adapter=adapter)
        result = await exe.screen_get_size()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_screen_capture_success(self) -> None:
        adapter = _MockPCControlAdapter()
        exe = PCControlExecutor(adapter=adapter)
        result = await exe.screen_capture()
        assert result.status == "success"

    def test_is_available_true(self) -> None:
        adapter = _MockPCControlAdapter(available=True)
        exe = PCControlExecutor(adapter=adapter)
        assert exe.is_available is True

    def test_is_available_false(self) -> None:
        adapter = LocalPCControlAdapter()
        exe = PCControlExecutor(adapter=adapter)
        assert exe.is_available is False


# =========================================================================
# PCControlManager — ModuleInterface lifecycle
# =========================================================================


class TestPCControlManagerLifecycle:
    @pytest.mark.asyncio
    async def test_initial_state(self) -> None:
        mgr = PCControlManager()
        assert mgr.degraded is False

    @pytest.mark.asyncio
    async def test_async_init_sets_up(self) -> None:
        mgr = PCControlManager()
        await mgr.async_init()
        assert mgr.degraded is False
        assert mgr.is_available is False

    @pytest.mark.asyncio
    async def test_shutdown_clears_state(self) -> None:
        mgr = PCControlManager()
        await mgr.async_init()
        await mgr.async_shutdown()
        assert mgr.degraded is False

    @pytest.mark.asyncio
    async def test_double_shutdown_is_safe(self) -> None:
        mgr = PCControlManager()
        await mgr.async_init()
        await mgr.async_shutdown()
        await mgr.async_shutdown()

    @pytest.mark.asyncio
    async def test_degrade_sets_flag(self) -> None:
        mgr = PCControlManager()
        await mgr.async_init()
        mgr.degrade()
        assert mgr.degraded is True

    @pytest.mark.asyncio
    async def test_double_degrade_is_safe(self) -> None:
        mgr = PCControlManager()
        mgr.degrade()
        mgr.degrade()
        assert mgr.degraded is True

    @pytest.mark.asyncio
    async def test_logger_injection(self) -> None:
        logger = MagicMock()
        mgr = PCControlManager(logger=logger)
        assert mgr._logger is logger

    @pytest.mark.asyncio
    async def test_with_adapter_injection(self) -> None:
        adapter = LocalPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        assert mgr._adapter is adapter


# =========================================================================
# PCControlManager — operation tests
# =========================================================================


class TestPCControlManagerOperations:
    @pytest.mark.asyncio
    async def test_mouse_get_position_with_adapter(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.mouse_get_position()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_mouse_get_position_no_adapter(self) -> None:
        mgr = PCControlManager()
        await mgr.async_init()
        result = await mgr.mouse_get_position()
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_mouse_move_to(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.mouse_move_to(100, 200)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_mouse_click(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.mouse_click()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_mouse_double_click(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.mouse_double_click()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_mouse_right_click(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.mouse_right_click()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_mouse_drag(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.mouse_drag(0, 0, 100, 100)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_mouse_scroll(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.mouse_scroll(1)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_keyboard_type_text(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.keyboard_type_text("hello")
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_keyboard_press_key(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.keyboard_press_key("enter")
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_keyboard_hotkey(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.keyboard_hotkey("ctrl", "c")
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_clipboard_get_text(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.clipboard_get_text()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_clipboard_set_text(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.clipboard_set_text("data")
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_clipboard_clear(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.clipboard_clear()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_filesystem_list_directory(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.filesystem_list_directory("/tmp")
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_filesystem_read_file(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.filesystem_read_file("/tmp/a.txt")
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_filesystem_write_file(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.filesystem_write_file("/tmp/a.txt", "data")
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_filesystem_delete_file(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.filesystem_delete_file("/tmp/a.txt")
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_filesystem_create_directory(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.filesystem_create_directory("/tmp/new")
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_window_list(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.window_list()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_window_get_active(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.window_get_active()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_window_focus(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.window_focus(1)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_window_minimize(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.window_minimize(1)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_window_maximize(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.window_maximize(1)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_window_close(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.window_close(1)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_window_resize(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.window_resize(1, 800, 600)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_window_move(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.window_move(1, 100, 100)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_process_list(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.process_list()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_process_kill(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.process_kill(1234)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_launch_application(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.launch_application("notepad.exe")
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_notification_show(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.notification_show("Title", "Message")
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_power_shutdown(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.power_shutdown()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_power_restart(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.power_restart()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_power_sleep(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.power_sleep()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_power_hibernate(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.power_hibernate()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_power_lock(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.power_lock()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_volume_get(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.volume_get()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_volume_set(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.volume_set(0.5)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_volume_mute(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.volume_mute(True)
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_screen_get_size(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.screen_get_size()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_screen_capture(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.screen_capture()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_screen_list_displays(self) -> None:
        adapter = _MockPCControlAdapter()
        mgr = PCControlManager(adapter=adapter)
        await mgr.async_init()
        result = await mgr.screen_list_displays()
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_degraded_raises(self) -> None:
        mgr = PCControlManager()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            await mgr.mouse_get_position()


# =========================================================================
# PCControlPort — ABC
# =========================================================================


class TestPCControlPortAbc:
    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError):
            PCControlPort()  # type: ignore[abstract]

    @pytest.mark.asyncio
    async def test_concrete_adapter(self) -> None:
        adapter = LocalPCControlAdapter()
        assert isinstance(adapter, PCControlPort)
        assert adapter.is_available is False


# =========================================================================
# ModuleInterface protocol conformance
# =========================================================================


class TestModuleInterfaceConformance:
    def test_pc_control_manager_conforms_to_protocol(self) -> None:
        assert isinstance(PCControlManager(), ModuleInterface)

    def test_pc_control_manager_has_required_methods(self) -> None:
        mgr = PCControlManager()
        assert hasattr(mgr, "async_init")
        assert hasattr(mgr, "async_shutdown")
        assert hasattr(mgr, "degrade")
