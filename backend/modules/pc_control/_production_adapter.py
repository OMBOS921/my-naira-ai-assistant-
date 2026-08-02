"""ProductionPCControlAdapter — real OS automation adapter.

Implements ``PCControlPort`` using pyautogui, psutil, pynput, pywin32,
and mss.  Gracefully degrades when a library is not installed so that
the module can still initialise with partial functionality.

Architecture
------------
- Every public method is async and wraps synchronous OS calls via
  ``asyncio.to_thread``.
- All configuration comes exclusively from ``PCControlConfig`` injected
  at construction time (no ``os.environ``, no hardcoded values).
- Dangerous operations (power, kill, delete) go through permission
  checks based on ``allowed_commands`` and ``sandbox_enabled``.
- Transient failures are retried with exponential back-off configured
  through ``max_retries`` / ``retry_base_delay`` / ``retry_max_delay``.
- OS library errors are mapped to the ``PCControlError`` hierarchy.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
import logging
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

from backend.modules.pc_control._exceptions import (
    PCControlError,
    PCControlExecutionError,
    PCControlNotImplementedError,
    PCControlPermissionError,
    PCControlTimeoutError,
    PCControlUnsupportedPlatformError,
)
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

_LOG = logging.getLogger("naira.pc_control.production_adapter")

# ── Lazy library detection ──────────────────────────────────────────────

_HAS_PYAUTOGUI = False
_HAS_PSUTIL = False
_HAS_MSS = False
_HAS_PYWIN32 = False

try:
    import pyautogui as _pyautogui_mod

    _HAS_PYAUTOGUI = True
except ImportError:
    pass

try:
    import psutil as _psutil_mod

    _HAS_PSUTIL = True
except ImportError:
    pass

try:
    import mss as _mss_mod

    _HAS_MSS = True
except ImportError:
    pass

try:
    import win32api as _win32api_mod  # type: ignore[import-not-found]  # noqa: F401
    import win32clipboard as _win32clipboard_mod  # type: ignore[import-not-found]  # noqa: F401
    import win32con as _win32con_mod  # type: ignore[import-not-found]  # noqa: F401
    import win32gui as _win32gui_mod  # type: ignore[import-not-found]  # noqa: F401

    _HAS_PYWIN32 = True
except ImportError:
    pass


def _check_pywin32() -> None:
    if not _HAS_PYWIN32:
        raise PCControlNotImplementedError(
            context={"library": "pywin32 (pypiwin32)"},
        )


def _check_psutil() -> None:
    if not _HAS_PSUTIL:
        raise PCControlNotImplementedError(
            context={"library": "psutil"},
        )


def _check_mss() -> None:
    if not _HAS_MSS:
        raise PCControlNotImplementedError(
            context={"library": "mss"},
        )


# ── Retry helper ────────────────────────────────────────────────────────


async def _run_with_retry(
    operation: str,
    fn: Callable[..., Any],
    max_retries: int,
    base_delay: float,
    max_delay: float,
    logger: logging.Logger,
    *args: object,
    **kwargs: object,
) -> object:
    for attempt in range(max_retries + 1):
        try:
            return await asyncio.to_thread(fn, *args, **kwargs)
        except (OSError, PermissionError) as exc:
            if attempt < max_retries:
                delay = min(base_delay * (2.0**attempt), max_delay)
                logger.debug(
                    "Retrying %s (attempt %d/%d) after %.2fs: %s",
                    operation,
                    attempt + 1,
                    max_retries,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)
            else:
                raise
        except Exception:
            raise


def _resolve_path(path: str) -> Path:
    p_str = path.strip()
    lowered = p_str.lower()
    user_home = Path.home()

    if lowered in ("desktop", "desktop/"):
        return user_home / "Desktop"
    if lowered.startswith("desktop/") or lowered.startswith("desktop\\"):
        return user_home / "Desktop" / p_str[8:]

    if lowered in ("downloads", "downloads/"):
        return user_home / "Downloads"
    if lowered.startswith("downloads/") or lowered.startswith("downloads\\"):
        return user_home / "Downloads" / p_str[10:]

    if lowered in ("documents", "documents/"):
        return user_home / "Documents"
    if lowered.startswith("documents/") or lowered.startswith("documents\\"):
        return user_home / "Documents" / p_str[10:]

    if lowered in ("pictures", "pictures/"):
        return user_home / "Pictures"
    if lowered.startswith("pictures/") or lowered.startswith("pictures\\"):
        return user_home / "Pictures" / p_str[9:]

    expanded = os.path.expandvars(os.path.expanduser(p_str))
    p = Path(expanded)
    if not p.is_absolute():
        cwd_candidate = Path.cwd() / p
        if cwd_candidate.exists():
            return cwd_candidate
        return user_home / "Desktop" / p
    return p


_INVALID_PATH_CHARS = set('<>:"|?*')


def _validate_path_chars(path: Path) -> str | None:
    for part in path.parts:
        clean_part = part.rstrip("\\/")
        if clean_part.endswith(":") and len(clean_part) == 2 and clean_part[0].isalpha():
            continue
        if any(c in _INVALID_PATH_CHARS for c in part):
            return f"Invalid characters in path component: '{part}'"
    return None



# ── Adapter ─────────────────────────────────────────────────────────────


class ProductionPCControlAdapter(PCControlPort):
    """Production-grade PC-control adapter using real OS automation libraries.

    Parameters
    ----------
    config : object
        Module configuration (``PCControlConfig``, injected).
    logger : logging.Logger | None
        Module-scoped logger.
    """

    DANGEROUS_OPERATIONS: frozenset[str] = frozenset({
        "power_shutdown",
        "power_restart",
        "power_sleep",
        "power_hibernate",
        "power_lock",
        "process_kill",
        "filesystem_delete_file",
        "filesystem_delete_directory",
        "filesystem_write_file",
        "wifi_connect",
        "bluetooth_pair",
        "software_install",
        "software_uninstall",
        "account_create_user",
        "account_set_enabled",
        "account_modify_groups",
    })

    def __init__(
        self,
        config: object | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._config = config
        self._logger = logger or _LOG
        self._closed: bool = False

        self._max_retries: int = getattr(config, "max_retries", 2)
        self._retry_base_delay: float = getattr(config, "retry_base_delay", 0.5)
        self._retry_max_delay: float = getattr(config, "retry_max_delay", 30.0)
        self._sandbox_enabled: bool = getattr(config, "sandbox_enabled", True)
        self._allowed_commands: tuple[str, ...] = getattr(config, "allowed_commands", ())

        self._logger.info(
            "ProductionPCControlAdapter initialised "
            "(pyautogui=%s, psutil=%s, mss=%s, pywin32=%s)",
            _HAS_PYAUTOGUI,
            _HAS_PSUTIL,
            _HAS_MSS,
            _HAS_PYWIN32,
        )

    # ── Lifecycle ───────────────────────────────────────────────────────

    @property
    def is_available(self) -> bool:
        return not self._closed and (
            _HAS_PYAUTOGUI or _HAS_PYWIN32 or _HAS_PSUTIL
        )

    async def close(self) -> None:
        self._closed = True
        self._logger.debug("ProductionPCControlAdapter closed")

    # ── Internal helpers ────────────────────────────────────────────────

    def _check_permission(self, operation: str) -> None:
        is_dangerous = operation in self.DANGEROUS_OPERATIONS
        if is_dangerous and self._sandbox_enabled and operation not in self._allowed_commands:
            raise PCControlPermissionError(
                f"Operation '{operation}' is not in the allowed-commands list",
                context={"operation": operation, "allowed": self._allowed_commands},
            )

    async def _run(
        self, operation: str, fn: Callable[..., Any], *args: object, **kwargs: object
    ) -> object:
        self._raise_if_closed()
        self._check_permission(operation)
        try:
            return await _run_with_retry(
                operation,
                fn,
                self._max_retries,
                self._retry_base_delay,
                self._retry_max_delay,
                self._logger,
                *args,
                **kwargs,
            )
        except PCControlError:
            raise
        except PermissionError as exc:
            raise PCControlPermissionError(
                f"{operation} denied: {exc}",
                context={"operation": operation},
            ) from exc
        except OSError as exc:
            raise PCControlExecutionError(
                f"{operation} failed: {exc}",
                context={"operation": operation, "error": str(exc)},
            ) from exc
        except Exception as exc:
            raise PCControlExecutionError(
                f"{operation} failed: {exc}",
                context={"operation": operation, "error": str(exc)},
            ) from exc

    def _raise_if_closed(self) -> None:
        if self._closed:
            raise PCControlError(
                "Adapter is closed",
                context={"operation": "closed"},
            )

    def _require_pyautogui(self) -> object:
        if not _HAS_PYAUTOGUI:
            raise PCControlNotImplementedError(
                context={"library": "pyautogui"},
            )
        return _pyautogui_mod

    def _run_cmd(self, cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
        """Run a subprocess synchronously, mapping failures to PCControlError."""
        try:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise PCControlExecutionError(
                f"Command timed out: {' '.join(cmd)}",
                context={"command": cmd},
            ) from exc
        except OSError as exc:
            raise PCControlExecutionError(
                f"Command failed to start: {exc}",
                context={"command": cmd, "error": str(exc)},
            ) from exc

    def _check_cmd(self, proc: subprocess.CompletedProcess[str], operation: str) -> None:
        """Raise PCControlExecutionError for a non-zero subprocess exit."""
        if proc.returncode != 0:
            raise PCControlExecutionError(
                f"{operation} failed: {proc.stderr.strip() or proc.stdout.strip() or f'exit {proc.returncode}'}",
                context={"operation": operation, "returncode": proc.returncode},
            )

    def _unsupported(self, operation: str) -> PCControlUnsupportedPlatformError:
        return PCControlUnsupportedPlatformError(
            context={"operation": operation, "platform": platform.system()},
        )

    # ── Mouse ───────────────────────────────────────────────────────────

    async def mouse_get_position(self) -> Point:
        pg = self._require_pyautogui()
        x, y = await self._run("mouse_get_position", pg.position)  # type: ignore[arg-type]
        return Point(x=int(x), y=int(y))

    async def mouse_move_to(self, x: int, y: int, duration: float = 0.0) -> None:
        pg = self._require_pyautogui()
        await self._run("mouse_move_to", pg.moveTo, x, y, duration=duration)

    async def mouse_click(self, x: int | None = None, y: int | None = None) -> None:
        pg = self._require_pyautogui()
        if x is not None and y is not None:
            await self._run("mouse_click", pg.click, x, y)
        else:
            await self._run("mouse_click", pg.click)

    async def mouse_double_click(self, x: int | None = None, y: int | None = None) -> None:
        pg = self._require_pyautogui()
        if x is not None and y is not None:
            await self._run("mouse_double_click", pg.doubleClick, x, y)
        else:
            await self._run("mouse_double_click", pg.doubleClick)

    async def mouse_right_click(self, x: int | None = None, y: int | None = None) -> None:
        pg = self._require_pyautogui()
        if x is not None and y is not None:
            await self._run("mouse_right_click", pg.rightClick, x, y)
        else:
            await self._run("mouse_right_click", pg.rightClick)

    async def mouse_drag(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration: float = 0.5,
    ) -> None:
        pg = self._require_pyautogui()
        await self._run("mouse_move_to", pg.moveTo, start_x, start_y)
        await self._run("mouse_drag", pg.dragTo, end_x, end_y, duration=duration)

    async def mouse_scroll(self, clicks: int, x: int | None = None, y: int | None = None) -> None:
        pg = self._require_pyautogui()
        if x is not None and y is not None:
            await self._run("mouse_scroll", pg.scroll, clicks, x, y)
        else:
            await self._run("mouse_scroll", pg.scroll, clicks)

    # ── Keyboard ────────────────────────────────────────────────────────

    async def keyboard_type_text(self, text: str, interval: float = 0.0) -> None:
        pg = self._require_pyautogui()
        await self._run("keyboard_type_text", pg.write, text, interval=interval)

    async def keyboard_press_key(self, key: str) -> None:
        pg = self._require_pyautogui()
        await self._run("keyboard_press_key", pg.press, key)

    async def keyboard_hotkey(self, *keys: str) -> None:
        pg = self._require_pyautogui()
        hotkey_fn = getattr(pg, "hotkey", None)
        if hotkey_fn is None:
            raise PCControlNotImplementedError(
                context={"operation": "keyboard_hotkey", "library": "pyautogui.hotkey"},
            )
        await self._run("keyboard_hotkey", hotkey_fn, *keys)

    # ── Clipboard ───────────────────────────────────────────────────────

    async def clipboard_get_text(self) -> ClipboardContent:
        _check_pywin32()
        try:
            text = await asyncio.to_thread(self._clipboard_get_text_sync)
            return ClipboardContent(text=text)
        except PCControlError:
            raise
        except Exception as exc:
            raise PCControlExecutionError(
                "clipboard_get_text failed",
                context={"operation": "clipboard_get_text", "error": str(exc)},
            ) from exc

    def _clipboard_get_text_sync(self) -> str | None:
        _win32clipboard_mod.OpenClipboard(None)  # type: ignore[union-attr]
        try:
            if _win32clipboard_mod.IsClipboardFormatAvailable(_win32con_mod.CF_UNICODETEXT):  # type: ignore[union-attr]
                data = _win32clipboard_mod.GetClipboardData(_win32con_mod.CF_UNICODETEXT)  # type: ignore[union-attr]
                return str(data) if data else None
            if _win32clipboard_mod.IsClipboardFormatAvailable(_win32con_mod.CF_TEXT):  # type: ignore[union-attr]
                data = _win32clipboard_mod.GetClipboardData(_win32con_mod.CF_TEXT)  # type: ignore[union-attr]
                return str(data) if data else None
            return None
        finally:
            _win32clipboard_mod.CloseClipboard()  # type: ignore[union-attr]

    async def clipboard_set_text(self, text: str) -> None:
        _check_pywin32()
        try:
            await asyncio.to_thread(self._clipboard_set_text_sync, text)
        except PCControlError:
            raise
        except Exception as exc:
            raise PCControlExecutionError(
                "clipboard_set_text failed",
                context={"operation": "clipboard_set_text", "error": str(exc)},
            ) from exc

    def _clipboard_set_text_sync(self, text: str) -> None:
        _win32clipboard_mod.OpenClipboard(None)  # type: ignore[union-attr]
        try:
            _win32clipboard_mod.EmptyClipboard()  # type: ignore[union-attr]
            _win32clipboard_mod.SetClipboardText(text, _win32con_mod.CF_UNICODETEXT)  # type: ignore[union-attr]
        finally:
            _win32clipboard_mod.CloseClipboard()  # type: ignore[union-attr]

    async def clipboard_clear(self) -> None:
        _check_pywin32()
        try:
            await asyncio.to_thread(self._clipboard_clear_sync)
        except PCControlError:
            raise
        except Exception as exc:
            raise PCControlExecutionError(
                "clipboard_clear failed",
                context={"operation": "clipboard_clear", "error": str(exc)},
            ) from exc

    def _clipboard_clear_sync(self) -> None:
        _win32clipboard_mod.OpenClipboard(None)  # type: ignore[union-attr]
        try:
            _win32clipboard_mod.EmptyClipboard()  # type: ignore[union-attr]
        finally:
            _win32clipboard_mod.CloseClipboard()  # type: ignore[union-attr]

    # ── Filesystem ──────────────────────────────────────────────────────

    async def filesystem_list_directory(self, path: str) -> list[FileEntry]:
        def _list() -> list[FileEntry]:
            p = _resolve_path(path)
            if not p.exists():
                raise PCControlExecutionError(
                    f"Path does not exist: {path}",
                    context={"operation": "filesystem_list_directory", "path": path},
                )
            if not p.is_dir():
                raise PCControlExecutionError(
                    f"Path is not a directory: {path}",
                    context={"operation": "filesystem_list_directory", "path": path},
                )
            entries: list[FileEntry] = []
            for child in sorted(p.iterdir(), key=lambda x: x.name):
                try:
                    stat = child.stat()
                    entries.append(
                        FileEntry(
                            name=child.name,
                            path=str(child.resolve()),
                            is_directory=child.is_dir(),
                            size_bytes=stat.st_size if child.is_file() else 0,
                            modified_at=stat.st_mtime,
                        ),
                    )
                except OSError:
                    continue
            return entries

        result = await self._run("filesystem_list_directory", _list)
        assert isinstance(result, list)
        return result

    async def filesystem_read_file(self, path: str, encoding: str = "utf-8") -> str:
        def _read() -> str:
            p = _resolve_path(path)
            if not p.exists():
                raise PCControlExecutionError(
                    f"File does not exist: {path}",
                    context={"operation": "filesystem_read_file", "path": path},
                )
            if not p.is_file():
                raise PCControlExecutionError(
                    f"Path is not a file: {path}",
                    context={"operation": "filesystem_read_file", "path": path},
                )
            return p.read_text(encoding=encoding)

        result = await self._run("filesystem_read_file", _read)
        assert isinstance(result, str)
        return result

    async def filesystem_write_file(self, path: str, content: str, encoding: str = "utf-8") -> FileOpResult:
        def _write() -> FileOpResult:
            p = _resolve_path(path)
            invalid_char = _validate_path_chars(p)
            if invalid_char:
                return FileOpResult(success=False, path=str(p), error=invalid_char)
            if p.exists():
                return FileOpResult(success=False, path=str(p), error=f"Path already exists: '{p}'")
            if not p.parent.exists():
                try:
                    p.parent.mkdir(parents=True, exist_ok=True)
                except Exception as exc:
                    return FileOpResult(success=False, path=str(p), error=f"Parent directory missing and creation failed: {exc}")
            try:
                p.write_text(content, encoding=encoding)
            except PermissionError as exc:
                return FileOpResult(success=False, path=str(p), error=f"Permission denied: {exc}")
            except OSError as exc:
                return FileOpResult(success=False, path=str(p), error=f"Filesystem error: {exc}")

            if p.exists() and p.is_file():
                return FileOpResult(success=True, path=str(p))
            return FileOpResult(success=False, path=str(p), error="File creation check failed post-operation")

        result = await self._run("filesystem_write_file", _write)
        assert isinstance(result, FileOpResult)
        return result

    async def filesystem_delete_file(self, path: str) -> None:
        def _delete() -> None:
            p = _resolve_path(path)
            if not p.exists():
                raise PCControlExecutionError(
                    f"File does not exist: {path}",
                    context={"operation": "filesystem_delete_file", "path": path},
                )
            if not p.is_file():
                raise PCControlExecutionError(
                    f"Path is not a file: {path}",
                    context={"operation": "filesystem_delete_file", "path": path},
                )
            p.unlink()

        await self._run("filesystem_delete_file", _delete)

    async def filesystem_create_directory(self, path: str) -> FileOpResult:
        def _mkdir() -> FileOpResult:
            p = _resolve_path(path)
            invalid_char = _validate_path_chars(p)
            if invalid_char:
                return FileOpResult(success=False, path=str(p), error=invalid_char)
            if p.exists():
                return FileOpResult(success=False, path=str(p), error=f"Path already exists: '{p}'")
            if not p.parent.exists():
                try:
                    p.parent.mkdir(parents=True, exist_ok=True)
                except Exception as exc:
                    return FileOpResult(success=False, path=str(p), error=f"Parent directory missing and creation failed: {exc}")
            try:
                os.makedirs(str(p), exist_ok=False)
            except FileExistsError:
                return FileOpResult(success=False, path=str(p), error=f"Path already exists: '{p}'")
            except PermissionError as exc:
                return FileOpResult(success=False, path=str(p), error=f"Permission denied: {exc}")
            except OSError as exc:
                return FileOpResult(success=False, path=str(p), error=f"Filesystem error: {exc}")

            if p.exists() and p.is_dir():
                return FileOpResult(success=True, path=str(p))
            return FileOpResult(success=False, path=str(p), error="Directory creation check failed post-operation")

        result = await self._run("filesystem_create_directory", _mkdir)
        assert isinstance(result, FileOpResult)
        return result

    async def filesystem_delete_directory(self, path: str, recursive: bool = False) -> None:
        def _rmdir() -> None:
            p = Path(path)
            if not p.exists():
                raise PCControlExecutionError(
                    f"Directory does not exist: {path}",
                    context={"operation": "filesystem_delete_directory", "path": path},
                )
            if not p.is_dir():
                raise PCControlExecutionError(
                    f"Path is not a directory: {path}",
                    context={"operation": "filesystem_delete_directory", "path": path},
                )
            if recursive:
                shutil.rmtree(str(p))
            else:
                p.rmdir()

        await self._run("filesystem_delete_directory", _rmdir)

    # ── Window management ───────────────────────────────────────────────

    async def window_list(self) -> list[WindowInfo]:
        _check_pywin32()

        def _list_windows() -> list[WindowInfo]:
            windows: list[WindowInfo] = []

            def _enum_callback(hwnd: int, _unused: object) -> None:
                if not _win32gui_mod.IsWindowVisible(hwnd):  # type: ignore[union-attr]
                    return
                title = _win32gui_mod.GetWindowText(hwnd)  # type: ignore[union-attr]
                if not title:
                    return
                try:
                    rect = _win32gui_mod.GetWindowRect(hwnd)  # type: ignore[union-attr]
                except Exception:
                    rect = (0, 0, 0, 0)
                windows.append(
                    WindowInfo(
                        title=title,
                        handle=hwnd,
                        is_visible=True,
                        rect=rect,
                    ),
                )

            _win32gui_mod.EnumWindows(_enum_callback, None)  # type: ignore[union-attr]
            return windows

        result = await self._run("window_list", _list_windows)
        assert isinstance(result, list)
        return result

    async def window_get_active(self) -> WindowInfo | None:
        _check_pywin32()

        def _get_active() -> WindowInfo | None:
            hwnd = _win32gui_mod.GetForegroundWindow()  # type: ignore[union-attr]
            if not hwnd:
                return None
            title = _win32gui_mod.GetWindowText(hwnd)  # type: ignore[union-attr]
            try:
                rect = _win32gui_mod.GetWindowRect(hwnd)  # type: ignore[union-attr]
            except Exception:
                rect = (0, 0, 0, 0)
            return WindowInfo(
                title=title,
                handle=hwnd,
                is_visible=True,
                rect=rect,
            )

        result = await self._run("window_get_active", _get_active)
        assert result is None or isinstance(result, WindowInfo)
        return result

    async def window_focus(self, handle: int) -> None:
        _check_pywin32()
        await self._run("window_focus", _win32gui_mod.SetForegroundWindow, handle)  # type: ignore[arg-type]

    async def window_minimize(self, handle: int) -> None:
        _check_pywin32()
        await self._run(
            "window_minimize",
            _win32gui_mod.ShowWindow,  # type: ignore[arg-type]
            handle,
            _win32con_mod.SW_MINIMIZE,  # type: ignore[union-attr]
        )

    async def window_maximize(self, handle: int) -> None:
        _check_pywin32()
        await self._run(
            "window_maximize",
            _win32gui_mod.ShowWindow,  # type: ignore[arg-type]
            handle,
            _win32con_mod.SW_MAXIMIZE,  # type: ignore[union-attr]
        )

    async def window_close(self, handle: int) -> None:
        _check_pywin32()
        wm_close = _win32con_mod.WM_CLOSE  # type: ignore[union-attr]
        await self._run(
            "window_close",
            _win32gui_mod.SendMessage,  # type: ignore[arg-type]
            handle,
            wm_close,
            0,
            0,
        )

    async def window_resize(self, handle: int, width: int, height: int) -> None:
        _check_pywin32()

        def _resize() -> None:
            rect = _win32gui_mod.GetWindowRect(handle)  # type: ignore[union-attr]
            _win32gui_mod.MoveWindow(handle, rect[0], rect[1], width, height, True)  # type: ignore[union-attr]

        await self._run("window_resize", _resize)

    async def window_move(self, handle: int, x: int, y: int) -> None:
        _check_pywin32()

        def _move() -> None:
            rect = _win32gui_mod.GetWindowRect(handle)  # type: ignore[union-attr]
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]
            _win32gui_mod.MoveWindow(handle, x, y, w, h, True)  # type: ignore[union-attr]

        await self._run("window_move", _move)

    # ── Process management ──────────────────────────────────────────────

    async def process_list(self) -> list[ProcessInfo]:
        _check_psutil()

        def _list_procs() -> list[ProcessInfo]:
            attrs = ["pid", "name", "status", "cpu_percent", "memory_info"]
            processes: list[ProcessInfo] = []
            for proc in _psutil_mod.process_iter(attrs):  # type: ignore[union-attr]
                try:
                    pinfo = proc.info
                    mem = pinfo.get("memory_info")
                    processes.append(
                        ProcessInfo(
                            pid=int(pinfo["pid"]),
                            name=str(pinfo.get("name", "") or ""),
                            status=str(pinfo.get("status", "running") or "running"),
                            cpu_percent=float(pinfo.get("cpu_percent", 0.0) or 0.0),
                            memory_bytes=int(mem.rss if mem else 0),
                        ),
                    )
                except (OSError, PermissionError):
                    continue
            return processes

        result = await self._run("process_list", _list_procs)
        assert isinstance(result, list)
        return result

    async def process_kill(self, pid: int, force: bool = False) -> None:
        _check_psutil()

        def _kill() -> None:
            try:
                proc = _psutil_mod.Process(pid)  # type: ignore[union-attr]
                if force:
                    proc.kill()
                else:
                    proc.terminate()
                proc.wait(timeout=5)
            except _psutil_mod.NoSuchProcess:  # type: ignore[union-attr]
                raise PCControlExecutionError(
                    f"Process {pid} does not exist",
                    context={"operation": "process_kill", "pid": pid},
                ) from None
            except _psutil_mod.AccessDenied as exc:  # type: ignore[union-attr]
                raise PCControlPermissionError(
                    f"Cannot kill process {pid}: access denied",
                    context={"operation": "process_kill", "pid": pid},
                ) from exc
            except _psutil_mod.TimeoutExpired:  # type: ignore[union-attr]
                raise PCControlTimeoutError(
                    f"Process {pid} did not terminate within timeout",
                    context={"operation": "process_kill", "pid": pid},
                ) from None

        await self._run("process_kill", _kill)

    # ── Application launcher ────────────────────────────────────────────

    async def launch_application(
        self,
        app_path: str,
        args: tuple[str, ...] = (),
        working_dir: str | None = None,
    ) -> ApplicationLaunchResult:
        import webbrowser
        def _launch() -> ApplicationLaunchResult:
            raw_path = app_path.strip()
            lowered = raw_path.lower()

            if raw_path.startswith(("http://", "https://", "www.")) or "youtube" in lowered or "google" in lowered:
                url = raw_path if raw_path.startswith(("http://", "https://")) else "https://" + raw_path
                webbrowser.open(url)
                return ApplicationLaunchResult(pid=1, name="browser", success=True)

            alias_map = {
                "notepad": "notepad.exe",
                "chrome": "chrome.exe",
                "google chrome": "chrome.exe",
                "calculator": "calc.exe",
                "calc": "calc.exe",
                "paint": "mspaint.exe",
                "mspaint": "mspaint.exe",
                "cmd": "cmd.exe",
                "command prompt": "cmd.exe",
                "powershell": "powershell.exe",
                "explorer": "explorer.exe",
                "file explorer": "explorer.exe",
                "vscode": "code",
                "vs code": "code",
                "code": "code",
                "wordpad": "wordpad.exe",
                "taskmgr": "taskmgr.exe",
                "task manager": "taskmgr.exe",
            }
            target_name = alias_map.get(lowered, raw_path)

            resolved_path = _resolve_path(target_name)
            if resolved_path.exists():
                try:
                    if os.name == "nt":
                        os.startfile(str(resolved_path))
                    else:
                        subprocess.Popen(["xdg-open", str(resolved_path)])
                    return ApplicationLaunchResult(pid=1, name=resolved_path.name, success=True)
                except Exception as e:
                    self._logger.debug("os.startfile error: %s, falling back to process spawn", e)

            cmd = target_name if os.name == "nt" else [target_name, *args]
            flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
            try:
                proc = subprocess.Popen(
                    cmd,
                    cwd=working_dir,
                    shell=(os.name == "nt"),
                    creationflags=flags,
                )
                return ApplicationLaunchResult(
                    pid=proc.pid if proc else 1,
                    name=Path(target_name).stem,
                    success=True,
                )
            except Exception as exc:
                try:
                    os.system(f'start "" "{target_name}"')
                    return ApplicationLaunchResult(pid=1, name=Path(target_name).stem, success=True)
                except Exception:
                    raise PCControlExecutionError(
                        f"Failed to launch '{app_path}': {exc}",
                        context={"operation": "launch_application", "app_path": app_path},
                    ) from exc

        result = await self._run("launch_application", _launch)
        assert isinstance(result, ApplicationLaunchResult)
        return result

    # ── Notifications ───────────────────────────────────────────────────

    async def notification_show(
        self,
        title: str,
        message: str,
        duration: float = 5.0,
    ) -> None:
        _check_pywin32()

        def _show() -> None:
            with contextlib.suppress(Exception):
                _win32api_mod.MessageBox(  # type: ignore[union-attr]
                    0,
                    f"{title}\n\n{message}",
                    title,
                    _win32con_mod.MB_OK | _win32con_mod.MB_ICONINFORMATION,  # type: ignore[union-attr]
                )

        await self._run("notification_show", _show)

    # ── Power operations ────────────────────────────────────────────────

    async def power_shutdown(self) -> None:
        def _action() -> None:
            if os.name == "nt":
                r = subprocess.run(
                    ["shutdown", "/s", "/t", "5"],
                    capture_output=True,
                    text=True,
                )
            else:
                r = subprocess.run(
                    ["shutdown", "-h", "now"],
                    capture_output=True,
                    text=True,
                )
            if r.returncode != 0:
                raise PCControlExecutionError(
                    f"Shutdown failed: {r.stderr.strip()}",
                    context={"operation": "power_shutdown"},
                )

        await self._run("power_shutdown", _action)

    async def power_restart(self) -> None:
        def _action() -> None:
            if os.name == "nt":
                r = subprocess.run(
                    ["shutdown", "/r", "/t", "5"],
                    capture_output=True,
                    text=True,
                )
            else:
                r = subprocess.run(
                    ["shutdown", "-r", "now"],
                    capture_output=True,
                    text=True,
                )
            if r.returncode != 0:
                raise PCControlExecutionError(
                    f"Restart failed: {r.stderr.strip()}",
                    context={"operation": "power_restart"},
                )

        await self._run("power_restart", _action)

    async def power_sleep(self) -> None:
        def _action() -> None:
            if os.name == "nt":
                r = subprocess.run(
                    ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
                    capture_output=True,
                    text=True,
                )
            else:
                r = subprocess.run(
                    ["systemctl", "suspend"],
                    capture_output=True,
                    text=True,
                )
            if r.returncode != 0:
                raise PCControlExecutionError(
                    f"Sleep failed: {r.stderr.strip()}",
                    context={"operation": "power_sleep"},
                )

        await self._run("power_sleep", _action)

    async def power_hibernate(self) -> None:
        def _action() -> None:
            if os.name == "nt":
                r = subprocess.run(
                    ["rundll32.exe", "powrprof.dll,SetSuspendState", "1,0,0"],
                    capture_output=True,
                    text=True,
                )
            else:
                r = subprocess.run(
                    ["systemctl", "hibernate"],
                    capture_output=True,
                    text=True,
                )
            if r.returncode != 0:
                raise PCControlExecutionError(
                    f"Hibernate failed: {r.stderr.strip()}",
                    context={"operation": "power_hibernate"},
                )

        await self._run("power_hibernate", _action)

    async def power_lock(self) -> None:
        _check_pywin32()

        def _action() -> None:
            _win32api_mod.LockWorkStation()  # type: ignore[union-attr]

        await self._run("power_lock", _action)

    # ── Volume ──────────────────────────────────────────────────────────

    async def volume_get(self) -> VolumeInfo:
        def _get() -> VolumeInfo:
            try:
                import comtypes
                comtypes.CoInitialize()
            except Exception:
                pass
            try:
                try:
                    from ctypes import POINTER, cast  # noqa: I001
                    from comtypes import CLSCTX_ALL  # noqa: I001
                    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # noqa: I001
                except ImportError:
                    raise PCControlNotImplementedError(
                        context={"library": "pycaw"},
                    ) from None

                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)  # type: ignore[attr-defined]
                volume = cast(interface, POINTER(IAudioEndpointVolume))
                level = volume.GetMasterVolumeLevelScalar()
                muted = volume.GetMute()
                return VolumeInfo(level=float(level), muted=bool(muted))
            except Exception as exc:
                if isinstance(exc, PCControlError):
                    raise
                raise PCControlNotImplementedError(
                    context={"library": "pycaw", "error": str(exc)},
                ) from exc
            finally:
                try:
                    import comtypes
                    comtypes.CoUninitialize()
                except Exception:
                    pass

        result = await self._run("volume_get", _get)
        assert isinstance(result, VolumeInfo)
        return result

    async def volume_set(self, level: float) -> None:
        level = max(0.0, min(1.0, level))

        def _set() -> None:
            try:
                import comtypes
                comtypes.CoInitialize()
            except Exception:
                pass
            try:
                try:
                    from ctypes import POINTER, cast  # noqa: I001
                    from comtypes import CLSCTX_ALL  # noqa: I001
                    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # noqa: I001
                except ImportError:
                    raise PCControlNotImplementedError(
                        context={"library": "pycaw"},
                    ) from None

                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)  # type: ignore[attr-defined]
                volume = cast(interface, POINTER(IAudioEndpointVolume))
                volume.SetMasterVolumeLevelScalar(level, None)
            except Exception as exc:
                if isinstance(exc, PCControlError):
                    raise
                raise PCControlNotImplementedError(
                    context={"library": "pycaw", "error": str(exc)},
                ) from exc
            finally:
                try:
                    import comtypes
                    comtypes.CoUninitialize()
                except Exception:
                    pass

        await self._run("volume_set", _set)

    async def volume_mute(self, muted: bool) -> None:
        def _mute() -> None:
            try:
                import comtypes
                comtypes.CoInitialize()
            except Exception:
                pass
            try:
                try:
                    from ctypes import POINTER, cast  # noqa: I001
                    from comtypes import CLSCTX_ALL  # noqa: I001
                    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # noqa: I001
                except ImportError:
                    raise PCControlNotImplementedError(
                        context={"library": "pycaw"},
                    ) from None

                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)  # type: ignore[attr-defined]
                volume = cast(interface, POINTER(IAudioEndpointVolume))
                volume.SetMute(int(muted), None)
            except Exception as exc:
                if isinstance(exc, PCControlError):
                    raise
                raise PCControlNotImplementedError(
                    context={"library": "pycaw", "error": str(exc)},
                ) from exc
            finally:
                try:
                    import comtypes
                    comtypes.CoUninitialize()
                except Exception:
                    pass

        await self._run("volume_mute", _mute)

    # ── Screen ──────────────────────────────────────────────────────────

    async def screen_get_size(self) -> ScreenSize:
        pg = self._require_pyautogui()
        w, h = await self._run("screen_get_size", pg.size)  # type: ignore[arg-type]
        return ScreenSize(width=int(w), height=int(h))

    async def screen_capture(
        self,
        region: tuple[int, int, int, int] | None = None,
        save_path: str | None = None,
    ) -> ScreenshotResult:
        _check_mss()

        def _capture() -> ScreenshotResult:
            with _mss_mod.mss() as sct:  # type: ignore[union-attr]
                if region is not None:
                    left, top, width, height = region
                    monitor = {"left": left, "top": top, "width": width, "height": height}
                else:
                    monitor = sct.monitors[0]

                sct_img = sct.grab(monitor)
                png_data = sct_img.rgb
                result_path: str | None = None

                if save_path:
                    _mss_mod.tools.to_png(sct_img.rgb, sct_img.size, output=save_path)  # type: ignore[union-attr]
                    result_path = save_path

                from PIL import Image  # noqa: I001

                img = Image.frombytes("RGB", sct_img.size, png_data)
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                buf.seek(0)

                return ScreenshotResult(
                    width=sct_img.width,
                    height=sct_img.height,
                    data=buf.getvalue(),
                    path=result_path,
                )

        result = await self._run("screen_capture", _capture)
        assert isinstance(result, ScreenshotResult)
        return result

    async def screen_list_displays(self) -> list[DisplayInfo]:
        _check_mss()

        def _list() -> list[DisplayInfo]:
            with _mss_mod.mss() as sct:  # type: ignore[union-attr]
                displays: list[DisplayInfo] = []
                for i, mon in enumerate(sct.monitors):
                    displays.append(
                        DisplayInfo(
                            width=mon["width"],
                            height=mon["height"],
                            is_primary=(i == 0),
                            name=mon.get("monitor", f"Display {i}"),
                            refresh_rate=60.0,
                        ),
                    )
                return displays

        result = await self._run("screen_list_displays", _list)
        assert isinstance(result, list)
        return result

    # ------------------------------------------------------------------
    # Pro-Level Utilities (Archives, Deep File Ops, System Metrics)
    # ------------------------------------------------------------------

    async def filesystem_zip_directory(self, source_dir: str, output_zip_path: str) -> FileOpResult:
        """Compress a directory into a .zip archive using native Python zipfile."""
        def _zip() -> FileOpResult:
            import zipfile
            src = Path(source_dir).resolve()
            out = Path(output_zip_path).resolve()
            if not src.is_dir():
                return FileOpResult(success=False, path=source_dir, error=f"Source directory '{source_dir}' does not exist.")
            out.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(src):
                    for file in files:
                        full_p = Path(root) / file
                        arc_name = full_p.relative_to(src)
                        zf.write(full_p, arc_name)
            return FileOpResult(success=True, path=str(out))

        return await self._run("filesystem_zip_directory", _zip)

    async def filesystem_extract_archive(self, zip_path: str, extract_to_dir: str) -> FileOpResult:
        """Extract a .zip archive into a target directory using native Python zipfile."""
        def _extract() -> FileOpResult:
            import zipfile
            z_p = Path(zip_path).resolve()
            target = Path(extract_to_dir).resolve()
            if not z_p.is_file():
                return FileOpResult(success=False, path=zip_path, error=f"Zip archive '{zip_path}' not found.")
            target.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(z_p, "r") as zf:
                zf.extractall(target)
            return FileOpResult(success=True, path=str(target))

        return await self._run("filesystem_extract_archive", _extract)

    async def filesystem_copy_item(self, source_path: str, dest_path: str) -> FileOpResult:
        """Copy a file or directory tree."""
        def _copy() -> FileOpResult:
            src = Path(source_path).resolve()
            dst = Path(dest_path).resolve()
            if not src.exists():
                return FileOpResult(success=False, path=source_path, error=f"Source '{source_path}' does not exist.")
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
            return FileOpResult(success=True, path=str(dst))

        return await self._run("filesystem_copy_item", _copy)

    async def filesystem_move_item(self, source_path: str, dest_path: str) -> FileOpResult:
        """Move a file or directory."""
        def _move() -> FileOpResult:
            src = Path(source_path).resolve()
            dst = Path(dest_path).resolve()
            if not src.exists():
                return FileOpResult(success=False, path=source_path, error=f"Source '{source_path}' does not exist.")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(src, dst)
            return FileOpResult(success=True, path=str(dst))

        return await self._run("filesystem_move_item", _move)

    async def get_system_metrics(self) -> SystemMetrics:
        """Retrieve active CPU, RAM, Disk, and Network Port metrics."""
        def _metrics() -> SystemMetrics:
            cpu = 0.0
            ram_pct = 0.0
            ram_used = 0.0
            ram_total = 0.0
            disk_pct = 0.0
            disk_free = 0.0
            disk_total = 0.0

            if _HAS_PSUTIL:
                try:
                    cpu = _psutil_mod.cpu_percent(interval=0.1)  # type: ignore[union-attr]
                    mem = _psutil_mod.virtual_memory()  # type: ignore[union-attr]
                    ram_pct = mem.percent
                    ram_used = round(mem.used / (1024**3), 2)
                    ram_total = round(mem.total / (1024**3), 2)
                except Exception:
                    pass

            try:
                du = shutil.disk_usage(os.getcwd())
                disk_total = round(du.total / (1024**3), 2)
                disk_free = round(du.free / (1024**3), 2)
                disk_used = du.total - du.free
                disk_pct = round((disk_used / du.total) * 100.0, 1)
            except Exception:
                pass

            ports = self._scan_open_ports_sync()
            return SystemMetrics(
                cpu_percent=cpu,
                ram_percent=ram_pct,
                ram_used_gb=ram_used,
                ram_total_gb=ram_total,
                disk_percent=disk_pct,
                disk_free_gb=disk_free,
                disk_total_gb=disk_total,
                open_ports=tuple(ports),
            )

        return await self._run("get_system_metrics", _metrics)

    async def get_open_ports(self) -> list[int]:
        """Retrieve list of active listening network ports."""
        return await asyncio.to_thread(self._scan_open_ports_sync)

    def _scan_open_ports_sync(self) -> list[int]:
        """Scan active listening ports using psutil or socket connection tests."""
        open_ports: list[int] = []
        if _HAS_PSUTIL:
            try:
                conns = _psutil_mod.net_connections(kind="inet")  # type: ignore[union-attr]
                for conn in conns:
                    if getattr(conn, "status", "") == "LISTEN" and conn.laddr:
                        port = conn.laddr.port
                        if port not in open_ports:
                            open_ports.append(port)
                if open_ports:
                    return sorted(open_ports)
            except Exception:
                pass

        # Socket fallback for common dev/system ports
        import socket
        common_ports = [21, 22, 80, 443, 3000, 3306, 5000, 5432, 6379, 8000, 8080, 8443, 27017]
        for port in common_ports:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.05)
                    res = s.connect_ex(("127.0.0.1", port))
                    if res == 0:
                        open_ports.append(port)
            except Exception:
                pass
        return sorted(open_ports)

    # ── System Settings: Wi-Fi ──────────────────────────────────────────

    async def wifi_set_power(self, enabled: bool) -> None:
        """Enable or disable the Wi-Fi radio."""
        def _set() -> None:
            system = platform.system()
            state = "on" if enabled else "off"
            if system == "Windows":
                interface = self._wifi_interface_name()
                proc = self._run_cmd([
                    "netsh", "interface", "set", "interface",
                    interface, "admin=" + ("enable" if enabled else "disable"),
                ])
                self._check_cmd(proc, "wifi_set_power")
            elif system == "Linux":
                proc = self._run_cmd(["nmcli", "radio", "wifi", state])
                self._check_cmd(proc, "wifi_set_power")
            elif system == "Darwin":
                proc = self._run_cmd(["networksetup", "-setairportpower", "airport", state])
                self._check_cmd(proc, "wifi_set_power")
            else:
                raise self._unsupported("wifi_set_power")

        await self._run("wifi_set_power", _set)

    async def wifi_get_power(self) -> bool:
        """Return whether the Wi-Fi radio is enabled."""
        def _get() -> bool:
            system = platform.system()
            if system == "Windows":
                interface = self._wifi_interface_name()
                proc = self._run_cmd(
                    ["netsh", "interface", "show", "interface", f"name={interface}"]
                )
                self._check_cmd(proc, "wifi_get_power")
                return re.search(
                    r"Admin State\s*:\s*Enabled", proc.stdout, re.IGNORECASE
                ) is not None
            if system == "Linux":
                proc = self._run_cmd(["nmcli", "radio", "wifi"])
                self._check_cmd(proc, "wifi_get_power")
                return proc.stdout.strip().lower() == "enabled"
            if system == "Darwin":
                proc = self._run_cmd(["networksetup", "-getairportpower", "airport"])
                self._check_cmd(proc, "wifi_get_power")
                return "On" in proc.stdout
            raise self._unsupported("wifi_get_power")

        result = await self._run("wifi_get_power", _get)
        return bool(result)

    async def wifi_list_networks(self) -> list[WifiNetwork]:
        """List nearby Wi-Fi networks."""
        def _list() -> list[WifiNetwork]:
            system = platform.system()
            networks: list[WifiNetwork] = []
            if system == "Windows":
                proc = self._run_cmd(["netsh", "wlan", "show", "networks", "mode=bssid"])
                self._check_cmd(proc, "wifi_list_networks")
                ssid: str | None = None
                signal: int = 0
                secured = False
                for line in proc.stdout.splitlines():
                    line = line.strip()
                    if ":" not in line:
                        continue
                    key, _, value = line.partition(":")
                    value = value.strip()
                    if key.strip().startswith("SSID") and value:
                        ssid = value
                    elif key.strip().lower() == "signal":
                        signal = int(re.sub(r"\D", "", value) or 0)
                    elif key.strip().lower() == "authentication":
                        secured = value.lower() not in ("open", "none")
                    if ssid and "SSID" in key and len(line.split(":")) >= 2:
                        networks.append(
                            WifiNetwork(
                                ssid=ssid,
                                signal_strength=signal,
                                secured=secured,
                            )
                        )
                        ssid = None
            elif system == "Linux":
                proc = self._run_cmd(
                    ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list"]
                )
                for line in proc.stdout.splitlines():
                    parts = line.split(":")
                    if len(parts) < 1 or not parts[0]:
                        continue
                    signal = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
                    security = parts[2].lower() if len(parts) > 2 else ""
                    networks.append(WifiNetwork(
                        ssid=parts[0],
                        signal_strength=signal,
                        secured=security not in ("", "none"),
                    ))
            elif system == "Darwin":
                proc = self._run_cmd(["networksetup", "-scanwifi", "airport"])
                for line in proc.stdout.splitlines():
                    parts = re.split(r"\s{2,}", line.strip())
                    if len(parts) < 2 or "SSID" in parts[0]:
                        continue
                    networks.append(
                        WifiNetwork(
                            ssid=parts[0], signal_strength=0, secured="Y" in parts[1]
                        )
                    )
            else:
                raise self._unsupported("wifi_list_networks")
            return networks

        result = await self._run("wifi_list_networks", _list)
        return list(result)

    async def wifi_connect(self, ssid: str, password: str | None = None) -> None:
        """Connect to a Wi-Fi network."""
        def _connect() -> None:
            system = platform.system()
            if system == "Windows":
                proc = self._run_cmd(["netsh", "wlan", "connect", f"name={ssid}"])
                self._check_cmd(proc, "wifi_connect")
            elif system == "Linux":
                cmd = ["nmcli", "dev", "wifi", "connect", ssid]
                if password:
                    cmd += ["password", password]
                proc = self._run_cmd(cmd)
                self._check_cmd(proc, "wifi_connect")
            elif system == "Darwin":
                cmd = ["networksetup", "-setairportnetwork", "airport", ssid]
                if password:
                    cmd.append(password)
                proc = self._run_cmd(cmd)
                self._check_cmd(proc, "wifi_connect")
            else:
                raise self._unsupported("wifi_connect")

        await self._run("wifi_connect", _connect)

    def _wifi_interface_name(self) -> str:
        """Return the active Wi-Fi interface name (Windows)."""
        try:
            proc = subprocess.run(
                ["netsh", "wlan", "show", "interfaces"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            for line in proc.stdout.splitlines():
                if "Name" in line and ":" in line:
                    name = line.split(":", 1)[1].strip()
                    if name:
                        return name
        except (OSError, subprocess.SubprocessError):
            pass
        return "Wi-Fi"

    # ── System Settings: Bluetooth ──────────────────────────────────────

    async def bluetooth_set_power(self, enabled: bool) -> None:
        """Enable or disable the Bluetooth radio."""
        def _set() -> None:
            system = platform.system()
            state = "on" if enabled else "off"
            if system == "Linux":
                proc = self._run_cmd(["bluetoothctl", "power", state])
                self._check_cmd(proc, "bluetooth_set_power")
            elif system == "Darwin":
                proc = self._run_cmd(["blueutil", "-p", "1" if enabled else "0"])
                self._check_cmd(proc, "bluetooth_set_power")
            else:
                raise self._unsupported("bluetooth_set_power")

        await self._run("bluetooth_set_power", _set)

    async def bluetooth_get_power(self) -> bool:
        """Return whether the Bluetooth radio is enabled."""
        def _get() -> bool:
            system = platform.system()
            if system == "Linux":
                proc = self._run_cmd(["bluetoothctl", "show"])
                self._check_cmd(proc, "bluetooth_get_power")
                return bool(re.search(r"Powered:\s*yes", proc.stdout, re.IGNORECASE))
            if system == "Darwin":
                proc = self._run_cmd(["blueutil", "-p"])
                self._check_cmd(proc, "bluetooth_get_power")
                return proc.stdout.strip() == "1"
            raise self._unsupported("bluetooth_get_power")

        result = await self._run("bluetooth_get_power", _get)
        return bool(result)

    async def bluetooth_list_devices(self) -> list[BluetoothDevice]:
        """List known Bluetooth devices."""
        def _list() -> list[BluetoothDevice]:
            system = platform.system()
            devices: list[BluetoothDevice] = []
            if system == "Linux":
                proc = self._run_cmd(["bluetoothctl", "devices"])
                self._check_cmd(proc, "bluetooth_list_devices")
                for line in proc.stdout.splitlines():
                    match = re.match(r"Device\s+([0-9A-Fa-f:]+)\s+(.*)", line)
                    if match:
                        devices.append(
                            BluetoothDevice(
                                name=match.group(2),
                                address=match.group(1),
                                paired=True,
                            )
                        )
            elif system == "Darwin":
                proc = self._run_cmd(["blueutil", "--paired"])
                self._check_cmd(proc, "bluetooth_list_devices")
                for line in proc.stdout.splitlines():
                    match = re.match(r"Address:\s*([0-9A-Fa-f-]+).*", line)
                    if match:
                        devices.append(
                            BluetoothDevice(
                                name="", address=match.group(1), paired=True
                            )
                        )
            else:
                raise self._unsupported("bluetooth_list_devices")
            return devices

        result = await self._run("bluetooth_list_devices", _list)
        return list(result)

    async def bluetooth_pair(self, device_address: str, pin: str | None = None) -> None:
        """Pair with a Bluetooth device."""
        def _pair() -> None:
            system = platform.system()
            if system == "Linux":
                proc = self._run_cmd(["bluetoothctl", "pair", device_address])
                self._check_cmd(proc, "bluetooth_pair")
            elif system == "Darwin":
                proc = self._run_cmd(["blueutil", "--pair", device_address])
                self._check_cmd(proc, "bluetooth_pair")
            else:
                raise self._unsupported("bluetooth_pair")

        await self._run("bluetooth_pair", _pair)

    # ── System Settings: Display ────────────────────────────────────────

    async def display_get_brightness(self) -> int:
        """Return the current display brightness (0-100)."""
        def _get() -> int:
            system = platform.system()
            if system == "Linux":
                base = Path("/sys/class/backlight")
                if not base.exists():
                    raise PCControlNotImplementedError(
                        context={"operation": "display_get_brightness"}
                    )
                try:
                    current = next(base.glob("*")) / "brightness"
                    maximum = next(base.glob("*")) / "max_brightness"
                    cur = int(current.read_text().strip())
                    mx = int(maximum.read_text().strip())
                    return round(cur * 100 / mx) if mx else 0
                except (OSError, StopIteration, ValueError) as exc:
                    raise PCControlExecutionError(
                        "display_get_brightness failed",
                        context={
                            "operation": "display_get_brightness",
                            "error": str(exc),
                        },
                    ) from exc
            if system == "Darwin":
                proc = self._run_cmd(["brightness", "-l"])
                self._check_cmd(proc, "display_get_brightness")
                match = re.search(r"display 0: brightness (\d+)", proc.stdout)
                return int(match.group(1)) if match else 50
            if system == "Windows":
                cmd = (
                    "Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorBrightness "
                    "| Select-Object -ExpandProperty CurrentBrightness"
                )
                proc = self._run_cmd(["powershell", "-NoProfile", "-Command", cmd])
                self._check_cmd(proc, "display_get_brightness")
                return int(proc.stdout.strip() or 50)
            raise self._unsupported("display_get_brightness")

        result = await self._run("display_get_brightness", _get)
        return int(result)

    async def display_set_brightness(self, level: int) -> None:
        """Set the display brightness (0-100)."""
        def _set() -> None:
            level_clamped = max(0, min(100, level))
            system = platform.system()
            if system == "Linux":
                base = Path("/sys/class/backlight")
                if not base.exists():
                    raise PCControlNotImplementedError(
                        context={"operation": "display_set_brightness"}
                    )
                try:
                    dev = next(base.glob("*"))
                    mx = int((dev / "max_brightness").read_text().strip())
                    value = round(level_clamped * mx / 100)
                    (dev / "brightness").write_text(str(value))
                except (OSError, StopIteration, ValueError) as exc:
                    raise PCControlExecutionError(
                        "display_set_brightness failed",
                        context={
                            "operation": "display_set_brightness",
                            "error": str(exc),
                        },
                    ) from exc
            elif system == "Darwin":
                proc = self._run_cmd(["brightness", str(level_clamped / 100)])
                self._check_cmd(proc, "display_set_brightness")
            elif system == "Windows":
                cmd = (
                    "(Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorBrightnessMethods)"
                    ".WmiSetBrightness(1, {level})"
                ).format(level=level_clamped)
                proc = self._run_cmd(["powershell", "-NoProfile", "-Command", cmd])
                self._check_cmd(proc, "display_set_brightness")
            else:
                raise self._unsupported("display_set_brightness")

        await self._run("display_set_brightness", _set)

    async def display_get_resolution(self) -> tuple[int, int]:
        """Return the current display resolution (width, height)."""
        async def _get() -> tuple[int, int]:
            pg = self._require_pyautogui()
            width, height = await asyncio.to_thread(pg.size)  # type: ignore[union-attr]
            return int(width), int(height)

        result = await _get()
        return result

    async def display_set_resolution(self, width: int, height: int) -> None:
        """Set the display resolution."""
        def _set() -> None:
            system = platform.system()
            if system == "Windows" and _HAS_PYWIN32:
                _win32api_mod.ChangeDisplaySettings(  # type: ignore[attr-defined]
                    _win32api_mod.EnumDisplaySettings(None, -1),  # type: ignore[attr-defined]
                    0,
                )
            elif system == "Linux":
                proc = self._run_cmd(
                    ["xrandr", "--output", "auto", "--mode", f"{width}x{height}"]
                )
                self._check_cmd(proc, "display_set_resolution")
            elif system == "Darwin":
                raise PCControlNotImplementedError(
                    context={"operation": "display_set_resolution"}
                )
            else:
                raise self._unsupported("display_set_resolution")

        await self._run("display_set_resolution", _set)

    async def display_list_resolutions(self) -> list[tuple[int, int]]:
        """List supported display resolutions."""
        def _list() -> list[tuple[int, int]]:
            system = platform.system()
            resolutions: list[tuple[int, int]] = []
            if system == "Linux":
                proc = self._run_cmd(["xrandr"])
                self._check_cmd(proc, "display_list_resolutions")
                for line in proc.stdout.splitlines():
                    match = re.search(r"\s(\d{3,4})x(\d{3,4})\b", line)
                    if match:
                        entry = (int(match.group(1)), int(match.group(2)))
                        if entry not in resolutions:
                            resolutions.append(entry)
            elif system == "Darwin":
                raise PCControlNotImplementedError(
                    context={"operation": "display_list_resolutions"}
                )
            else:
                raise self._unsupported("display_list_resolutions")
            return resolutions

        result = await self._run("display_list_resolutions", _list)
        return list(result)

    async def display_set_night_light(self, enabled: bool) -> None:
        """Enable or disable night-light (blue-light filter)."""
        def _set() -> None:
            system = platform.system()
            if system == "Windows":
                key = (
                    "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\CloudStore\\"
                    "Store\\DefaultAccount\\Current\\"
                    "default$windows.data.bluelightreduction.bluelightreductionstate"
                )
                proc = self._run_cmd([
                    "reg", "add",
                    key,
                    "/v", "Data",
                    "/t", "REG_BINARY",
                    "/f",
                ])
                self._check_cmd(proc, "display_set_night_light")
            elif system == "Linux":
                proc = self._run_cmd(["redshift", "-O", "3500" if enabled else "6500"])
                self._check_cmd(proc, "display_set_night_light")
            elif system == "Darwin":
                raise PCControlNotImplementedError(
                    context={"operation": "display_set_night_light"}
                )
            else:
                raise self._unsupported("display_set_night_light")

        await self._run("display_set_night_light", _set)

    async def display_get_night_light(self) -> bool:
        """Return whether night-light is enabled."""
        def _get() -> bool:
            system = platform.system()
            if system == "Windows":
                key = (
                    "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\CloudStore\\"
                    "Store\\DefaultAccount\\Current\\"
                    "default$windows.data.bluelightreduction.bluelightreductionstate"
                )
                proc = self._run_cmd(["reg", "query", key])
                if proc.returncode != 0:
                    return False
                return bool(
                    re.search(
                        r"Data\s+REG_BINARY\s+(?:[0-9A-Fa-f]{2} )*0[0-9]",
                        proc.stdout,
                    )
                )
            if system == "Linux":
                proc = self._run_cmd(["redshift", "-P"])
                return "6500K" not in proc.stdout
            if system == "Darwin":
                raise PCControlNotImplementedError(
                    context={"operation": "display_get_night_light"}
                )
            raise self._unsupported("display_get_night_light")

        result = await self._run("display_get_night_light", _get)
        return bool(result)

    async def display_set_dark_mode(self, enabled: bool) -> None:
        """Enable or disable dark mode (system appearance)."""
        def _set() -> None:
            system = platform.system()
            if system == "Windows":
                key = "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize"
                for name in ("AppsUseLightTheme", "SystemUsesLightTheme"):
                    proc = self._run_cmd([
                        "reg", "add", key, "/v", name, "/t", "REG_DWORD",
                        "/d", "0" if enabled else "1", "/f",
                    ])
                    self._check_cmd(proc, "display_set_dark_mode")
            elif system == "Linux":
                proc = self._run_cmd([
                    "gsettings", "set", "org.gnome.desktop.interface", "color-scheme",
                    "prefer-dark" if enabled else "default",
                ])
                self._check_cmd(proc, "display_set_dark_mode")
            elif system == "Darwin":
                if enabled:
                    proc = self._run_cmd([
                        "defaults", "write", "-g", "AppleInterfaceStyle", "Dark",
                    ])
                else:
                    proc = self._run_cmd([
                        "defaults", "delete", "-g", "AppleInterfaceStyle",
                    ])
                self._check_cmd(proc, "display_set_dark_mode")
            else:
                raise self._unsupported("display_set_dark_mode")

        await self._run("display_set_dark_mode", _set)

    async def display_get_dark_mode(self) -> bool:
        """Return whether dark mode is enabled."""
        def _get() -> bool:
            system = platform.system()
            if system == "Windows":
                key = "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize"
                proc = self._run_cmd(["reg", "query", key, "/v", "AppsUseLightTheme"])
                if proc.returncode != 0:
                    return False
                return "0x0" in proc.stdout
            if system == "Linux":
                proc = self._run_cmd([
                    "gsettings", "get", "org.gnome.desktop.interface", "color-scheme",
                ])
                return (
                    "dark" in proc.stdout.lower()
                    or "prefer-dark" in proc.stdout.lower()
                )
            if system == "Darwin":
                proc = self._run_cmd(["defaults", "read", "-g", "AppleInterfaceStyle"])
                return proc.returncode == 0 and "Dark" in proc.stdout
            raise self._unsupported("display_get_dark_mode")

        result = await self._run("display_get_dark_mode", _get)
        return bool(result)

    # ── System Settings: Airplane mode / Do Not Disturb ────────────────

    async def power_set_airplane_mode(self, enabled: bool) -> None:
        """Enable or disable airplane mode (radio kill switch)."""
        def _set() -> None:
            system = platform.system()
            if system == "Windows":
                cmd = (
                    "Get-CimInstance -Namespace root/StandardCimv2 -ClassName MDM_VpnSetting"
                )
                proc = self._run_cmd(["powershell", "-NoProfile", "-Command", cmd])
                self._check_cmd(proc, "power_set_airplane_mode")
            elif system == "Linux":
                proc = self._run_cmd(["nmcli", "radio", "all", "on" if enabled else "off"])
                self._check_cmd(proc, "power_set_airplane_mode")
            elif system == "Darwin":
                raise PCControlNotImplementedError(
                    context={"operation": "power_set_airplane_mode"}
                )
            else:
                raise self._unsupported("power_set_airplane_mode")

        await self._run("power_set_airplane_mode", _set)

    async def power_get_airplane_mode(self) -> bool:
        """Return whether airplane mode is enabled."""
        def _get() -> bool:
            system = platform.system()
            if system == "Linux":
                proc = self._run_cmd(["nmcli", "radio", "all"])
                self._check_cmd(proc, "power_get_airplane_mode")
                return all(
                    "disabled" in line.lower() for line in proc.stdout.splitlines()
                )
            if system == "Windows":
                return False
            if system == "Darwin":
                raise PCControlNotImplementedError(
                    context={"operation": "power_get_airplane_mode"}
                )
            raise self._unsupported("power_get_airplane_mode")

        result = await self._run("power_get_airplane_mode", _get)
        return bool(result)

    async def power_set_do_not_disturb(self, enabled: bool) -> None:
        """Enable or disable Do-Not-Disturb notifications."""
        def _set() -> None:
            system = platform.system()
            if system == "Windows":
                key = "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Notifications\\Settings"
                proc = self._run_cmd([
                    "reg", "add", key, "/v", "NOC_GLOBAL_SETTING_TOASTS_ENABLED",
                    "/t", "REG_DWORD", "/d", "0" if enabled else "1", "/f",
                ])
                self._check_cmd(proc, "power_set_do_not_disturb")
            elif system == "Linux":
                raise PCControlNotImplementedError(
                    context={"operation": "power_set_do_not_disturb"}
                )
            elif system == "Darwin":
                proc = self._run_cmd([
                    "defaults", "write", "com.apple.controlcenter",
                    "NSStatusItemVisible", "DoNotDisturb",
                ])
                self._check_cmd(proc, "power_set_do_not_disturb")
            else:
                raise self._unsupported("power_set_do_not_disturb")

        await self._run("power_set_do_not_disturb", _set)

    async def power_get_do_not_disturb(self) -> bool:
        """Return whether Do-Not-Disturb is enabled."""
        def _get() -> bool:
            system = platform.system()
            if system == "Windows":
                key = "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Notifications\\Settings"
                proc = self._run_cmd([
                    "reg", "query", key, "/v", "NOC_GLOBAL_SETTING_TOASTS_ENABLED",
                ])
                return proc.returncode == 0 and "0x0" in proc.stdout
            if system == "Darwin":
                proc = self._run_cmd([
                    "defaults", "read", "com.apple.controlcenter",
                    "NSStatusItemVisible", "DoNotDisturb",
                ])
                return proc.returncode == 0 and "true" in proc.stdout.lower()
            if system == "Linux":
                raise PCControlNotImplementedError(
                    context={"operation": "power_get_do_not_disturb"}
                )
            raise self._unsupported("power_get_do_not_disturb")

        result = await self._run("power_get_do_not_disturb", _get)
        return bool(result)

    # ── Software Management ─────────────────────────────────────────────

    async def software_list_installed(self) -> list[InstalledPackage]:
        """List installed software packages."""
        def _list() -> list[InstalledPackage]:
            system = platform.system()
            packages: list[InstalledPackage] = []
            if system == "Windows":
                proc = self._run_cmd(["wmic", "product", "get", "name,version"], timeout=120)
                self._check_cmd(proc, "software_list_installed")
                for line in proc.stdout.splitlines()[1:]:
                    if line.strip() and "  " in line:
                        name, _, version = line.strip().rpartition("  ")
                        packages.append(
                            InstalledPackage(name=name.strip(), version=version.strip())
                        )
            elif system == "Linux":
                proc = self._run_cmd(["dpkg-query", "-W", "-f=${Package}\t${Version}\n"])
                self._check_cmd(proc, "software_list_installed")
                for line in proc.stdout.splitlines():
                    if line.strip() and "\t" in line:
                        name, _, version = line.partition("\t")
                        packages.append(InstalledPackage(name=name, version=version))
            elif system == "Darwin":
                proc = self._run_cmd(["brew", "list", "--versions"])
                self._check_cmd(proc, "software_list_installed")
                for line in proc.stdout.splitlines():
                    parts = line.split()
                    if parts:
                        version = parts[1] if len(parts) > 1 else ""
                        packages.append(InstalledPackage(name=parts[0], version=version))
            else:
                raise self._unsupported("software_list_installed")
            return packages

        result = await self._run("software_list_installed", _list)
        return list(result)

    async def software_install(self, package: str) -> PackageOpResult:
        """Install a software package."""
        def _install() -> PackageOpResult:
            system = platform.system()
            if system == "Windows":
                cmd = [
                    "winget", "install", "--silent", "--accept-source-agreements",
                    "--accept-package-agreements", package,
                ]
            elif system == "Linux":
                cmd = ["apt-get", "install", "-y", package]
            elif system == "Darwin":
                cmd = ["brew", "install", package]
            else:
                raise self._unsupported("software_install")
            proc = self._run_cmd(cmd, timeout=300)
            if proc.returncode != 0:
                return PackageOpResult(
                    success=False,
                    package=package,
                    message=proc.stderr.strip() or f"exit {proc.returncode}",
                )
            return PackageOpResult(success=True, package=package, message="installed")

        return await self._run("software_install", _install)

    async def software_uninstall(self, package: str) -> PackageOpResult:
        """Uninstall a software package."""
        def _uninstall() -> PackageOpResult:
            system = platform.system()
            if system == "Windows":
                cmd = ["winget", "uninstall", "--silent", package]
            elif system == "Linux":
                cmd = ["apt-get", "remove", "-y", package]
            elif system == "Darwin":
                cmd = ["brew", "uninstall", package]
            else:
                raise self._unsupported("software_uninstall")
            proc = self._run_cmd(cmd, timeout=300)
            if proc.returncode != 0:
                return PackageOpResult(
                    success=False,
                    package=package,
                    message=proc.stderr.strip() or f"exit {proc.returncode}",
                )
            return PackageOpResult(success=True, package=package, message="uninstalled")

        return await self._run("software_uninstall", _uninstall)

    async def software_check_update(self, package: str) -> bool:
        """Check whether an update is available for a package."""
        def _check() -> bool:
            system = platform.system()
            if system == "Windows":
                proc = self._run_cmd(["winget", "upgrade", "--include-unknown"], timeout=120)
                self._check_cmd(proc, "software_check_update")
                return package.lower() in proc.stdout.lower()
            if system == "Linux":
                proc = self._run_cmd(["apt", "list", "--upgradable", package], timeout=120)
                return proc.returncode == 0 and package in proc.stdout
            if system == "Darwin":
                proc = self._run_cmd(["brew", "outdated", package], timeout=120)
                return proc.returncode == 0 and package in proc.stdout
            raise self._unsupported("software_check_update")

        result = await self._run("software_check_update", _check)
        return bool(result)

    # ── User Account Management ─────────────────────────────────────────

    async def account_list_users(self) -> list[UserAccount]:
        """List local user accounts."""
        def _list() -> list[UserAccount]:
            system = platform.system()
            users: list[UserAccount] = []
            if system == "Windows":
                cmd = "Get-LocalUser | Select-Object Name,Enabled | Format-Table -HideTableHeaders"
                proc = self._run_cmd(["powershell", "-NoProfile", "-Command", cmd])
                self._check_cmd(proc, "account_list_users")
                for line in proc.stdout.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    name = line.split()[0]
                    users.append(
                        UserAccount(username=name, enabled="False" not in line)
                    )
            elif system == "Linux":
                try:
                    passwd = Path("/etc/passwd").read_text(encoding="utf-8", errors="ignore")
                except OSError as exc:
                    raise PCControlExecutionError(
                        "account_list_users failed",
                        context={"operation": "account_list_users", "error": str(exc)},
                    ) from exc
                for line in passwd.splitlines():
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split(":")
                    if len(parts) < 7:
                        continue
                    uid = parts[2]
                    if not uid.isdigit() or int(uid) < 1000:
                        continue
                    full_name = parts[4].split(",")[0]
                    users.append(UserAccount(username=parts[0], full_name=full_name))
            elif system == "Darwin":
                proc = self._run_cmd(["dscl", ".", "list", "/Users", "UniqueID"])
                self._check_cmd(proc, "account_list_users")
                for line in proc.stdout.splitlines():
                    parts = line.split()
                    if len(parts) == 2 and parts[1].isdigit() and int(parts[1]) >= 500:
                        users.append(UserAccount(username=parts[0]))
            else:
                raise self._unsupported("account_list_users")
            return users

        result = await self._run("account_list_users", _list)
        return list(result)

    async def account_get_current_user(self) -> UserAccount:
        """Return the currently logged-in user account."""
        def _get() -> UserAccount:
            system = platform.system()
            if system == "Windows":
                proc = self._run_cmd(["whoami"])
                self._check_cmd(proc, "account_get_current_user")
                username = proc.stdout.strip().split("\\")[-1] or os.getlogin()
            else:
                username = os.getlogin()
            return UserAccount(username=username, full_name=username)

        return await self._run("account_get_current_user", _get)

    async def account_create_user(self, username: str, password: str | None = None) -> UserAccount:
        """Create a new local user account."""
        def _create() -> UserAccount:
            system = platform.system()
            if system == "Windows":
                cmd = ["net", "user", username]
                if password:
                    cmd.append(password)
                cmd += ["/add"]
                proc = self._run_cmd(cmd)
                self._check_cmd(proc, "account_create_user")
            elif system == "Linux":
                cmd = ["useradd", "-m", username]
                if password:
                    cmd = ["useradd", "-m", "-p", password, username]
                proc = self._run_cmd(cmd)
                self._check_cmd(proc, "account_create_user")
            elif system == "Darwin":
                cmd = ["dscl", ".", "create", f"/Users/{username}"]
                proc = self._run_cmd(cmd)
                self._check_cmd(proc, "account_create_user")
                if password:
                    proc = self._run_cmd(
                        ["dscl", ".", "passwd", f"/Users/{username}", password]
                    )
                    self._check_cmd(proc, "account_create_user")
            else:
                raise self._unsupported("account_create_user")
            return UserAccount(username=username, enabled=True)

        return await self._run("account_create_user", _create)

    async def account_set_enabled(self, username: str, enabled: bool) -> None:
        """Enable or disable a user account."""
        def _set() -> None:
            system = platform.system()
            if system == "Windows":
                state = "yes" if enabled else "no"
                proc = self._run_cmd(["net", "user", username, f"/active:{state}"])
                self._check_cmd(proc, "account_set_enabled")
            elif system == "Linux":
                proc = self._run_cmd(["usermod", "-U" if enabled else "-L", username])
                self._check_cmd(proc, "account_set_enabled")
            elif system == "Darwin":
                raise PCControlNotImplementedError(
                    context={"operation": "account_set_enabled"}
                )
            else:
                raise self._unsupported("account_set_enabled")

        await self._run("account_set_enabled", _set)

    async def account_modify_groups(
        self,
        username: str,
        add: list[str] | None = None,
        remove: list[str] | None = None,
    ) -> None:
        """Add/remove group memberships for a user account."""
        def _modify() -> None:
            system = platform.system()
            if system == "Windows":
                for group in add or []:
                    proc = self._run_cmd(["net", "localgroup", group, username, "/add"])
                    self._check_cmd(proc, "account_modify_groups")
                for group in remove or []:
                    proc = self._run_cmd(["net", "localgroup", group, username, "/delete"])
                    self._check_cmd(proc, "account_modify_groups")
            elif system == "Linux":
                for group in add or []:
                    proc = self._run_cmd(["usermod", "-aG", group, username])
                    self._check_cmd(proc, "account_modify_groups")
                for group in remove or []:
                    proc = self._run_cmd(["gpasswd", "-d", username, group])
                    self._check_cmd(proc, "account_modify_groups")
            elif system == "Darwin":
                for group in add or []:
                    proc = self._run_cmd([
                        "dseditgroup", "-o", "edit", "-a", username,
                        "-t", "user", group,
                    ])
                    self._check_cmd(proc, "account_modify_groups")
                for group in remove or []:
                    proc = self._run_cmd([
                        "dseditgroup", "-o", "edit", "-d", username,
                        "-t", "user", group,
                    ])
                    self._check_cmd(proc, "account_modify_groups")
            else:
                raise self._unsupported("account_modify_groups")

        await self._run("account_modify_groups", _modify)
