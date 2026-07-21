"""Comprehensive tests for ProductionPCControlAdapter.

Covers all 11 capability domains, permission checks, retry logic,
error mapping, partial-library scenarios, and the is_available/close
lifecycle.

All OS libraries are mocked — no real OS actions are executed.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.modules.pc_control._exceptions import (
    PCControlError,
    PCControlExecutionError,
    PCControlNotImplementedError,
    PCControlPermissionError,
)

# ── Helpers ─────────────────────────────────────────────────────────────


def _make_config(**overrides: object) -> MagicMock:
    """Create a mock PCControlConfig with test defaults."""
    config = MagicMock()
    config.default_timeout = 30.0
    config.enabled = True
    config.allowed_commands = (
        "filesystem_write_file",
        "filesystem_delete_file",
        "filesystem_delete_directory",
        "process_kill",
        "power_shutdown",
        "power_restart",
        "power_sleep",
        "power_hibernate",
        "power_lock",
    )
    config.sandbox_enabled = True
    config.max_retries = 1
    config.retry_base_delay = 0.1
    config.retry_max_delay = 1.0
    for k, v in overrides.items():
        setattr(config, k, v)
    return config


class _PsutilMock:
    """A mock for psutil that has real exception subclasses."""

    class NoSuchProcess(Exception):
        pass

    class AccessDenied(Exception):
        pass

    class TimeoutExpired(Exception):
        pass

    def __init__(self) -> None:
        self.Process = MagicMock()
        self.process_iter = MagicMock(return_value=[])


@pytest.fixture
def mock_libs() -> None:
    """Patch all OS library flags and references to enable full functionality."""
    psutil_mock = _PsutilMock()
    patchers = [
        patch("backend.modules.pc_control._production_adapter._HAS_PYAUTOGUI", True),
        patch("backend.modules.pc_control._production_adapter._pyautogui_mod", MagicMock(), create=True),
        patch("backend.modules.pc_control._production_adapter._HAS_PSUTIL", True),
        patch("backend.modules.pc_control._production_adapter._psutil_mod", psutil_mock, create=True),
        patch("backend.modules.pc_control._production_adapter._HAS_MSS", True),
        patch("backend.modules.pc_control._production_adapter._mss_mod", MagicMock(), create=True),
        patch("backend.modules.pc_control._production_adapter._HAS_PYWIN32", True),
        patch("backend.modules.pc_control._production_adapter._win32api_mod", MagicMock(), create=True),
        patch("backend.modules.pc_control._production_adapter._win32clipboard_mod", MagicMock(), create=True),
        patch("backend.modules.pc_control._production_adapter._win32con_mod", MagicMock(), create=True),
        patch("backend.modules.pc_control._production_adapter._win32gui_mod", MagicMock(), create=True),
    ]
    for p in patchers:
        p.start()
    yield psutil_mock
    for p in patchers:
        p.stop()


@pytest.fixture
def adapter(mock_libs: object) -> MagicMock:
    from backend.modules.pc_control._production_adapter import ProductionPCControlAdapter

    return ProductionPCControlAdapter(config=_make_config())  # type: ignore[return-value]


# =========================================================================
# Lifecycle
# =========================================================================


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_is_available_with_libs(self, adapter: MagicMock) -> None:
        assert adapter.is_available is True

    def test_is_available_no_libs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import backend.modules.pc_control._production_adapter as mod
        monkeypatch.setattr(mod, "_HAS_PYAUTOGUI", False)
        monkeypatch.setattr(mod, "_HAS_PSUTIL", False)
        monkeypatch.setattr(mod, "_HAS_MSS", False)
        monkeypatch.setattr(mod, "_HAS_PYWIN32", False)

        a = mod.ProductionPCControlAdapter(config=_make_config())
        assert a.is_available is False

    @pytest.mark.asyncio
    async def test_close_sets_closed(self, adapter: MagicMock) -> None:
        await adapter.close()
        assert adapter.is_available is False

    @pytest.mark.asyncio
    async def test_close_idempotent(self, adapter: MagicMock) -> None:
        await adapter.close()
        await adapter.close()

    @pytest.mark.asyncio
    async def test_operation_after_close_raises(self, adapter: MagicMock) -> None:
        await adapter.close()
        with pytest.raises(PCControlError, match="closed"):
            await adapter.mouse_get_position()


# =========================================================================
# Mouse
# =========================================================================


class TestMouse:
    @pytest.mark.asyncio
    async def test_get_position(self, adapter: MagicMock) -> None:
        _pyautogui().position.return_value = (100, 200)
        result = await adapter.mouse_get_position()
        assert result.x == 100
        assert result.y == 200

    @pytest.mark.asyncio
    async def test_move_to(self, adapter: MagicMock) -> None:
        pg = _pyautogui()
        await adapter.mouse_move_to(100, 200, duration=0.5)
        pg.moveTo.assert_called_once_with(100, 200, duration=0.5)

    @pytest.mark.asyncio
    async def test_click(self, adapter: MagicMock) -> None:
        pg = _pyautogui()
        await adapter.mouse_click()
        pg.click.assert_called_once()

    @pytest.mark.asyncio
    async def test_click_at_position(self, adapter: MagicMock) -> None:
        pg = _pyautogui()
        await adapter.mouse_click(50, 60)
        pg.click.assert_called_once_with(50, 60)

    @pytest.mark.asyncio
    async def test_double_click(self, adapter: MagicMock) -> None:
        pg = _pyautogui()
        await adapter.mouse_double_click()
        pg.doubleClick.assert_called_once()

    @pytest.mark.asyncio
    async def test_right_click(self, adapter: MagicMock) -> None:
        pg = _pyautogui()
        await adapter.mouse_right_click()
        pg.rightClick.assert_called_once()

    @pytest.mark.asyncio
    async def test_drag(self, adapter: MagicMock) -> None:
        pg = _pyautogui()
        await adapter.mouse_drag(10, 20, 100, 200, duration=0.3)
        pg.moveTo.assert_called_once_with(10, 20)
        pg.dragTo.assert_called_once_with(100, 200, duration=0.3)

    @pytest.mark.asyncio
    async def test_scroll(self, adapter: MagicMock) -> None:
        pg = _pyautogui()
        await adapter.mouse_scroll(3)
        pg.scroll.assert_called_once_with(3)

    @pytest.mark.asyncio
    async def test_scroll_at_position(self, adapter: MagicMock) -> None:
        pg = _pyautogui()
        await adapter.mouse_scroll(-1, 100, 200)
        pg.scroll.assert_called_once_with(-1, 100, 200)


# =========================================================================
# Keyboard
# =========================================================================


class TestKeyboard:
    @pytest.mark.asyncio
    async def test_type_text(self, adapter: MagicMock) -> None:
        pg = _pyautogui()
        await adapter.keyboard_type_text("hello", interval=0.05)
        pg.write.assert_called_once_with("hello", interval=0.05)

    @pytest.mark.asyncio
    async def test_press_key(self, adapter: MagicMock) -> None:
        pg = _pyautogui()
        await adapter.keyboard_press_key("enter")
        pg.press.assert_called_once_with("enter")

    @pytest.mark.asyncio
    async def test_hotkey(self, adapter: MagicMock) -> None:
        pg = _pyautogui()
        pg.hotkey = MagicMock()
        await adapter.keyboard_hotkey("ctrl", "c")
        pg.hotkey.assert_called_once_with("ctrl", "c")


# =========================================================================
# Clipboard
# =========================================================================


class TestClipboard:
    @pytest.mark.asyncio
    async def test_get_text(self, adapter: MagicMock) -> None:
        wc = _clipboard()
        wc.IsClipboardFormatAvailable.return_value = True
        wc.GetClipboardData.return_value = "clip text"
        result = await adapter.clipboard_get_text()
        assert result.text == "clip text"
        wc.OpenClipboard.assert_called_once()
        wc.CloseClipboard.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_text_none(self, adapter: MagicMock) -> None:
        wc = _clipboard()
        wc.IsClipboardFormatAvailable.return_value = False
        result = await adapter.clipboard_get_text()
        assert result.text is None

    @pytest.mark.asyncio
    async def test_set_text(self, adapter: MagicMock) -> None:
        wc = _clipboard()
        await adapter.clipboard_set_text("test data")
        wc.EmptyClipboard.assert_called_once()
        wc.SetClipboardText.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear(self, adapter: MagicMock) -> None:
        wc = _clipboard()
        await adapter.clipboard_clear()
        wc.EmptyClipboard.assert_called_once()


# =========================================================================
# Filesystem
# =========================================================================


class TestFilesystem:
    @pytest.mark.asyncio
    async def test_list_directory(self, adapter: MagicMock, tmp_path: object) -> None:
        import pathlib
        d = pathlib.Path(str(tmp_path))
        (d / "a.txt").write_text("a")
        (d / "sub").mkdir()
        result = await adapter.filesystem_list_directory(str(d))
        names = {e.name for e in result}
        assert "a.txt" in names
        assert "sub" in names

    @pytest.mark.asyncio
    async def test_list_directory_not_found(self, adapter: MagicMock) -> None:
        with pytest.raises(PCControlExecutionError, match="does not exist"):
            await adapter.filesystem_list_directory("/nonexistent_path_xyzzy")

    @pytest.mark.asyncio
    async def test_read_file(self, adapter: MagicMock, tmp_path: object) -> None:
        import pathlib
        f = pathlib.Path(str(tmp_path)) / "test.txt"
        f.write_text("hello world")
        content = await adapter.filesystem_read_file(str(f))
        assert content == "hello world"

    @pytest.mark.asyncio
    async def test_read_file_not_found(self, adapter: MagicMock) -> None:
        with pytest.raises(PCControlExecutionError, match="does not exist"):
            await adapter.filesystem_read_file("/nonexistent.txt")

    @pytest.mark.asyncio
    async def test_write_file(self, adapter: MagicMock, tmp_path: object) -> None:
        import pathlib
        f = pathlib.Path(str(tmp_path)) / "out.txt"
        await adapter.filesystem_write_file(str(f), "written content")
        assert f.read_text() == "written content"

    @pytest.mark.asyncio
    async def test_delete_file(self, adapter: MagicMock, tmp_path: object) -> None:
        import pathlib
        f = pathlib.Path(str(tmp_path)) / "to_delete.txt"
        f.write_text("delete me")
        await adapter.filesystem_delete_file(str(f))
        assert not f.exists()

    @pytest.mark.asyncio
    async def test_delete_file_not_found(self, adapter: MagicMock) -> None:
        with pytest.raises(PCControlExecutionError, match="does not exist"):
            await adapter.filesystem_delete_file("/nonexistent.txt")

    @pytest.mark.asyncio
    async def test_create_directory(self, adapter: MagicMock, tmp_path: object) -> None:
        import pathlib
        d = pathlib.Path(str(tmp_path)) / "new_dir"
        await adapter.filesystem_create_directory(str(d))
        assert d.is_dir()

    @pytest.mark.asyncio
    async def test_delete_directory(self, adapter: MagicMock, tmp_path: object) -> None:
        import pathlib
        d = pathlib.Path(str(tmp_path)) / "dir_to_delete"
        d.mkdir()
        (d / "nested").mkdir()
        (d / "nested" / "f.txt").write_text("x")
        await adapter.filesystem_delete_directory(str(d), recursive=True)
        assert not d.exists()

    @pytest.mark.asyncio
    async def test_delete_directory_not_found(self, adapter: MagicMock) -> None:
        with pytest.raises(PCControlExecutionError, match="does not exist"):
            await adapter.filesystem_delete_directory("/nonexistent_dir")


# =========================================================================
# Window management
# =========================================================================


class TestWindow:
    @pytest.mark.asyncio
    async def test_list(self, adapter: MagicMock) -> None:
        wg = _gui()
        wg.IsWindowVisible.return_value = True
        wg.GetWindowText.return_value = "Test Window"
        wg.GetWindowRect.return_value = (0, 0, 800, 600)

        def enum_callback(callback: object, _unused: object) -> None:
            callback(1001, None)  # type: ignore[misc]
            callback(1002, None)  # type: ignore[misc]

        wg.EnumWindows = enum_callback

        result = await adapter.window_list()
        assert len(result) == 2
        assert result[0].handle == 1001
        assert result[0].title == "Test Window"

    @pytest.mark.asyncio
    async def test_get_active(self, adapter: MagicMock) -> None:
        wg = _gui()
        wg.GetForegroundWindow.return_value = 5001
        wg.GetWindowText.return_value = "Active Win"
        wg.GetWindowRect.return_value = (10, 10, 500, 400)
        result = await adapter.window_get_active()
        assert result is not None
        assert result.handle == 5001
        assert result.title == "Active Win"

    @pytest.mark.asyncio
    async def test_get_active_none(self, adapter: MagicMock) -> None:
        wg = _gui()
        wg.GetForegroundWindow.return_value = 0
        result = await adapter.window_get_active()
        assert result is None

    @pytest.mark.asyncio
    async def test_focus(self, adapter: MagicMock) -> None:
        wg = _gui()
        await adapter.window_focus(100)
        wg.SetForegroundWindow.assert_called_once_with(100)

    @pytest.mark.asyncio
    async def test_minimize(self, adapter: MagicMock) -> None:
        wg = _gui()
        wc = _con()
        await adapter.window_minimize(200)
        wg.ShowWindow.assert_called_once_with(200, wc.SW_MINIMIZE)

    @pytest.mark.asyncio
    async def test_maximize(self, adapter: MagicMock) -> None:
        wg = _gui()
        wc = _con()
        await adapter.window_maximize(300)
        wg.ShowWindow.assert_called_once_with(300, wc.SW_MAXIMIZE)

    @pytest.mark.asyncio
    async def test_close(self, adapter: MagicMock) -> None:
        wg = _gui()
        wc = _con()
        await adapter.window_close(400)
        wg.SendMessage.assert_called_once_with(400, wc.WM_CLOSE, 0, 0)

    @pytest.mark.asyncio
    async def test_resize(self, adapter: MagicMock) -> None:
        wg = _gui()
        wg.GetWindowRect.return_value = (100, 200, 800, 600)
        await adapter.window_resize(500, 1024, 768)
        wg.MoveWindow.assert_called_once_with(500, 100, 200, 1024, 768, True)

    @pytest.mark.asyncio
    async def test_move(self, adapter: MagicMock) -> None:
        wg = _gui()
        wg.GetWindowRect.return_value = (0, 0, 800, 600)
        await adapter.window_move(600, 50, 100)
        wg.MoveWindow.assert_called_once_with(600, 50, 100, 800, 600, True)


# =========================================================================
# Process management
# =========================================================================


class TestProcess:
    @pytest.mark.asyncio
    async def test_list(self, adapter: MagicMock) -> None:
        ps = _psutil()
        proc_mock = MagicMock()
        proc_mock.info = {
            "pid": 1234,
            "name": "python.exe",
            "status": "running",
            "cpu_percent": 2.5,
            "memory_info": MagicMock(rss=10_485_760),
        }
        ps.process_iter.return_value = [proc_mock]
        result = await adapter.process_list()
        assert len(result) == 1
        assert result[0].pid == 1234
        assert result[0].name == "python.exe"
        assert result[0].cpu_percent == 2.5
        assert result[0].memory_bytes == 10_485_760

    @pytest.mark.asyncio
    async def test_kill(self, adapter: MagicMock) -> None:
        ps = _psutil()
        proc_mock = MagicMock()
        ps.Process.return_value = proc_mock
        await adapter.process_kill(9999)
        ps.Process.assert_called_once_with(9999)
        proc_mock.terminate.assert_called_once()
        proc_mock.wait.assert_called_once_with(timeout=5)

    @pytest.mark.asyncio
    async def test_kill_force(self, adapter: MagicMock) -> None:
        ps = _psutil()
        proc_mock = MagicMock()
        ps.Process.return_value = proc_mock
        await adapter.process_kill(1111, force=True)
        proc_mock.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_kill_not_found(self, adapter: MagicMock) -> None:
        ps = _psutil()
        ps.Process.side_effect = _PsutilMock.NoSuchProcess(9999)
        with pytest.raises(PCControlExecutionError, match="does not exist"):
            await adapter.process_kill(9999)


# =========================================================================
# Application launcher
# =========================================================================


class TestApplicationLauncher:
    @pytest.mark.asyncio
    async def test_launch(self, adapter: MagicMock) -> None:
        with patch("subprocess.Popen") as mock_popen:
            proc_mock = MagicMock()
            proc_mock.pid = 7777
            mock_popen.return_value = proc_mock
            result = await adapter.launch_application("notepad.exe", args=("test.txt",))
            assert result.pid == 7777
            assert result.name == "notepad"
            assert result.success is True


# =========================================================================
# Notifications
# =========================================================================


class TestNotification:
    @pytest.mark.asyncio
    async def test_show(self, adapter: MagicMock) -> None:
        wa = _api()
        await adapter.notification_show("Title", "Message body", duration=3.0)
        wa.MessageBox.assert_called_once()


# =========================================================================
# Power operations
# =========================================================================


class TestPower:
    @pytest.mark.asyncio
    async def test_shutdown(self, adapter: MagicMock) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            await adapter.power_shutdown()
            mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_restart(self, adapter: MagicMock) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            await adapter.power_restart()
            mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_sleep(self, adapter: MagicMock) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            await adapter.power_sleep()
            mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_hibernate(self, adapter: MagicMock) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            await adapter.power_hibernate()
            mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_lock(self, adapter: MagicMock) -> None:
        wa = _api()
        await adapter.power_lock()
        wa.LockWorkStation.assert_called_once()


# =========================================================================
# Screen
# =========================================================================


class TestScreen:
    @pytest.mark.asyncio
    async def test_get_size(self, adapter: MagicMock) -> None:
        pg = _pyautogui()
        pg.size.return_value = (1920, 1080)
        result = await adapter.screen_get_size()
        assert result.width == 1920
        assert result.height == 1080

    @pytest.mark.asyncio
    async def test_capture(self, adapter: MagicMock) -> None:
        mss = _mss()
        sct_instance = MagicMock()
        mss.mss.return_value.__enter__.return_value = sct_instance

        sct_img = MagicMock()
        sct_img.width = 800
        sct_img.height = 600
        sct_img.rgb = b"rgbdata"
        sct_img.size = (800, 600)
        sct_instance.grab.return_value = sct_img

        with patch.dict("sys.modules", {"PIL": MagicMock(), "PIL.Image": MagicMock()}):
            result = await adapter.screen_capture()
            assert result.width == 800
            assert result.height == 600
            assert isinstance(result.data, bytes)

    @pytest.mark.asyncio
    async def test_list_displays(self, adapter: MagicMock) -> None:
        mss = _mss()
        sct_instance = MagicMock()
        mss.mss.return_value.__enter__.return_value = sct_instance
        sct_instance.monitors = [
            {"left": 0, "top": 0, "width": 1920, "height": 1080},
            {"left": 0, "top": 0, "width": 1920, "height": 1080},
        ]
        result = await adapter.screen_list_displays()
        assert len(result) == 2


# =========================================================================
# Volume
# =========================================================================


class TestVolume:
    @pytest.mark.asyncio
    async def test_get_without_pycaw_raises(self, adapter: MagicMock) -> None:
        with pytest.raises(PCControlNotImplementedError, match="not available"):
            await adapter.volume_get()

    @pytest.mark.asyncio
    async def test_set_without_pycaw_raises(self, adapter: MagicMock) -> None:
        with pytest.raises(PCControlNotImplementedError, match="not available"):
            await adapter.volume_set(0.5)

    @pytest.mark.asyncio
    async def test_mute_without_pycaw_raises(self, adapter: MagicMock) -> None:
        with pytest.raises(PCControlNotImplementedError, match="not available"):
            await adapter.volume_mute(True)


# =========================================================================
# Permission checks
# =========================================================================


class TestPermissions:
    @pytest.mark.asyncio
    async def test_blocked_dangerous_operation_raises(self) -> None:
        config = _make_config(allowed_commands=(), sandbox_enabled=True)
        from backend.modules.pc_control._production_adapter import (
            ProductionPCControlAdapter,
        )

        adapter = ProductionPCControlAdapter(config=config)
        with pytest.raises(PCControlPermissionError, match="not in the allowed-commands"):
            adapter._check_permission("power_shutdown")  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_allowed_dangerous_operation_passes(self) -> None:
        config = _make_config(allowed_commands=("power_shutdown",), sandbox_enabled=True)
        from backend.modules.pc_control._production_adapter import (
            ProductionPCControlAdapter,
        )

        adapter = ProductionPCControlAdapter(config=config)
        adapter._check_permission("power_shutdown")  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_sandbox_disabled_allows_all(self) -> None:
        config = _make_config(allowed_commands=(), sandbox_enabled=False)
        from backend.modules.pc_control._production_adapter import (
            ProductionPCControlAdapter,
        )

        adapter = ProductionPCControlAdapter(config=config)
        adapter._check_permission("power_shutdown")  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_safe_operation_allowed(self) -> None:
        config = _make_config(allowed_commands=(), sandbox_enabled=True)
        from backend.modules.pc_control._production_adapter import (
            ProductionPCControlAdapter,
        )

        adapter = ProductionPCControlAdapter(config=config)
        adapter._check_permission("mouse_get_position")  # noqa: SLF001


# =========================================================================
# Error mapping
# =========================================================================


class TestErrorMapping:
    @pytest.mark.asyncio
    async def test_os_error_mapped(self, adapter: MagicMock) -> None:
        pg = _pyautogui()
        pg.position.side_effect = OSError("device unavailable")
        with pytest.raises(PCControlExecutionError, match="device unavailable"):
            await adapter.mouse_get_position()

    @pytest.mark.asyncio
    async def test_permission_error_mapped(self, adapter: MagicMock) -> None:
        pg = _pyautogui()
        pg.position.side_effect = PermissionError("access denied")
        with pytest.raises(PCControlPermissionError, match="access denied"):
            await adapter.mouse_get_position()


# =========================================================================
# Library not available
# =========================================================================


class TestMissingLibraries:
    @pytest.fixture(autouse=True)
    def mock_no_libs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import backend.modules.pc_control._production_adapter as mod
        monkeypatch.setattr(mod, "_HAS_PYAUTOGUI", False)
        monkeypatch.setattr(mod, "_HAS_PSUTIL", False)
        monkeypatch.setattr(mod, "_HAS_MSS", False)
        monkeypatch.setattr(mod, "_HAS_PYWIN32", False)

    @pytest.mark.asyncio
    async def test_mouse_without_pyautogui_raises(self) -> None:
        from backend.modules.pc_control._production_adapter import (
            ProductionPCControlAdapter,
        )

        adapter = ProductionPCControlAdapter(config=_make_config())
        with pytest.raises(PCControlNotImplementedError, match="not available"):
            await adapter.mouse_get_position()

    @pytest.mark.asyncio
    async def test_clipboard_without_pywin32_raises(self) -> None:
        from backend.modules.pc_control._production_adapter import (
            ProductionPCControlAdapter,
        )

        adapter = ProductionPCControlAdapter(config=_make_config())
        with pytest.raises(PCControlNotImplementedError, match="not available"):
            await adapter.clipboard_get_text()

    @pytest.mark.asyncio
    async def test_window_without_pywin32_raises(self) -> None:
        from backend.modules.pc_control._production_adapter import (
            ProductionPCControlAdapter,
        )

        adapter = ProductionPCControlAdapter(config=_make_config())
        with pytest.raises(PCControlNotImplementedError, match="not available"):
            await adapter.window_list()


# =========================================================================
# Helpers
# =========================================================================


def _pyautogui() -> MagicMock:
    import backend.modules.pc_control._production_adapter as mod
    return mod._pyautogui_mod


def _psutil() -> MagicMock:
    import backend.modules.pc_control._production_adapter as mod
    return mod._psutil_mod


def _mss() -> MagicMock:
    import backend.modules.pc_control._production_adapter as mod
    return mod._mss_mod


def _clipboard() -> MagicMock:
    import backend.modules.pc_control._production_adapter as mod
    return mod._win32clipboard_mod


def _gui() -> MagicMock:
    import backend.modules.pc_control._production_adapter as mod
    return mod._win32gui_mod


def _con() -> MagicMock:
    import backend.modules.pc_control._production_adapter as mod
    return mod._win32con_mod


def _api() -> MagicMock:
    import backend.modules.pc_control._production_adapter as mod
    return mod._win32api_mod
