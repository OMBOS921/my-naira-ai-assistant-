"""PC Control types — immutable result dataclasses for OS automation.

21_System_Contracts.md §15 — Tool contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Point:
    """A 2D screen coordinate.

    Parameters
    ----------
    x : int
        Horizontal pixel coordinate.
    y : int
        Vertical pixel coordinate.
    """

    x: int
    y: int


@dataclass(frozen=True)
class ScreenSize:
    """Screen or display resolution.

    Parameters
    ----------
    width : int
        Pixel width.
    height : int
        Pixel height.
    """

    width: int
    height: int


@dataclass(frozen=True)
class FileEntry:
    """A single file or directory entry.

    Parameters
    ----------
    name : str
        File or directory name.
    path : str
        Absolute path.
    is_directory : bool
        Whether this entry is a directory.
    size_bytes : int
        File size in bytes (0 for directories).
    modified_at : float
        Last modification timestamp (Unix epoch).
    """

    name: str
    path: str
    is_directory: bool
    size_bytes: int = 0
    modified_at: float = 0.0


@dataclass(frozen=True)
class ProcessInfo:
    """Snapshot of a running process.

    Parameters
    ----------
    pid : int
        Process identifier.
    name : str
        Process executable name.
    status : str
        Process status string (e.g. "running", "sleeping").
    cpu_percent : float
        CPU utilisation percentage.
    memory_bytes : int
        Resident memory usage in bytes.
    """

    pid: int
    name: str
    status: str = "running"
    cpu_percent: float = 0.0
    memory_bytes: int = 0


@dataclass(frozen=True)
class WindowInfo:
    """Snapshot of an OS window.

    Parameters
    ----------
    title : str
        Window title text.
    handle : int
        Native window handle identifier.
    is_visible : bool
        Whether the window is currently visible.
    rect : tuple[int, int, int, int]
        Window bounding rectangle ``(left, top, right, bottom)``.
    """

    title: str
    handle: int
    is_visible: bool = True
    rect: tuple[int, int, int, int] = (0, 0, 0, 0)


@dataclass(frozen=True)
class DisplayInfo:
    """Information about a display monitor.

    Parameters
    ----------
    width : int
        Display pixel width.
    height : int
        Display pixel height.
    is_primary : bool
        Whether this is the primary display.
    name : str
        Display / monitor name.
    refresh_rate : float
        Refresh rate in Hz.
    """

    width: int
    height: int
    is_primary: bool = False
    name: str = ""
    refresh_rate: float = 60.0


@dataclass(frozen=True)
class ClipboardContent:
    """Clipboard content snapshot.

    Parameters
    ----------
    text : str | None
        Text content if available.
    """

    text: str | None = None


@dataclass(frozen=True)
class VolumeInfo:
    """System volume state.

    Parameters
    ----------
    level : float
        Volume level (0.0 – 1.0).
    muted : bool
        Whether the audio output is muted.
    """

    level: float
    muted: bool


@dataclass(frozen=True)
class ScreenshotResult:
    """Result of a screen capture operation.

    Parameters
    ----------
    width : int
        Image width in pixels.
    height : int
        Image height in pixels.
    data : bytes
        PNG-encoded image bytes.
    path : str | None
        File path if saved to disk.
    """

    width: int
    height: int
    data: bytes
    path: str | None = None


@dataclass(frozen=True)
class ApplicationLaunchResult:
    """Result of launching an application.

    Parameters
    ----------
    pid : int
        Process ID of the launched application.
    name : str
        Application name.
    success : bool
        Whether the launch was successful.
    """

    pid: int
    name: str
    success: bool = True


@dataclass
class FileOpResult:
    """Result of a file or directory filesystem operation.

    Parameters
    ----------
    success : bool
        Whether the operation succeeded.
    path : str
        Target file or directory path.
    error : str | None
        Error message if operation failed.
    """

    success: bool
    path: str
    error: str | None = None


@dataclass(frozen=True)
class SystemMetrics:
    """Snapshot of active system hardware metrics and network status.

    Parameters
    ----------
    cpu_percent : float
        Overall CPU utilization percentage.
    ram_percent : float
        RAM utilization percentage.
    ram_used_gb : float
        Used RAM in Gigabytes.
    ram_total_gb : float
        Total RAM in Gigabytes.
    disk_percent : float
        Primary disk utilization percentage.
    disk_free_gb : float
        Free disk space in Gigabytes.
    disk_total_gb : float
        Total disk space in Gigabytes.
    open_ports : tuple[int, ...]
        List of active listening network ports.
    """

    cpu_percent: float = 0.0
    ram_percent: float = 0.0
    ram_used_gb: float = 0.0
    ram_total_gb: float = 0.0
    disk_percent: float = 0.0
    disk_free_gb: float = 0.0
    disk_total_gb: float = 0.0
    open_ports: tuple[int, ...] = ()


type PCControlAction = Literal[
    "mouse_move",
    "mouse_click",
    "mouse_double_click",
    "mouse_right_click",
    "mouse_drag",
    "mouse_scroll",
    "keyboard_type",
    "keyboard_press",
    "keyboard_hotkey",
    "clipboard_get",
    "clipboard_set",
    "clipboard_clear",
    "filesystem_list",
    "filesystem_read",
    "filesystem_write",
    "filesystem_delete",
    "filesystem_create_dir",
    "window_list",
    "window_focus",
    "window_resize",
    "window_move",
    "window_close",
    "process_list",
    "process_kill",
    "launch_application",
    "notification_show",
    "power_shutdown",
    "power_restart",
    "power_sleep",
    "power_hibernate",
    "power_lock",
    "volume_get",
    "volume_set",
    "volume_mute",
    "screen_capture",
    "screen_info",
]
"""Types of PC-control actions tracked by the module."""
