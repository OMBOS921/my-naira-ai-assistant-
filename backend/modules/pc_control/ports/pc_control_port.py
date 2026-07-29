"""PCControlPort — abstract port for pluggable PC-control adapters.

20_Dependency_Rules.md §2 — Port/Adapter pattern.

Concrete adapters (pyautogui, pynput, psutil, etc.) implement this
ABC so ``PCControlManager`` remains agnostic of the underlying driver.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.modules.pc_control._types import (
    ApplicationLaunchResult,
    ClipboardContent,
    DisplayInfo,
    FileEntry,
    FileOpResult,
    Point,
    ProcessInfo,
    ScreenshotResult,
    ScreenSize,
    VolumeInfo,
    WindowInfo,
)


class PCControlPort(ABC):
    """Abstract PC-control port.

    Each method corresponds to a high-level OS automation capability.
    Implementations manage their own driver lifecycle internally.
    """

    # ------------------------------------------------------------------
    # Mouse
    # ------------------------------------------------------------------

    @abstractmethod
    async def mouse_get_position(self) -> Point:
        """Get the current mouse cursor position.

        Returns
        -------
        Point
            Cursor coordinates.

        Raises
        ------
        PCControlExecutionError
            If the position cannot be read.
        """

    @abstractmethod
    async def mouse_move_to(self, x: int, y: int, duration: float = 0.0) -> None:
        """Move the mouse cursor to *(x, y)*.

        Parameters
        ----------
        x : int
            Target x-coordinate.
        y : int
            Target y-coordinate.
        duration : float
            Movement duration in seconds (0 = instant).

        Raises
        ------
        PCControlExecutionError
            If the move fails.
        """

    @abstractmethod
    async def mouse_click(self, x: int | None = None, y: int | None = None) -> None:
        """Click the primary mouse button.

        Parameters
        ----------
        x : int | None
            Optional x-coordinate to move to before clicking.
        y : int | None
            Optional y-coordinate to move to before clicking.

        Raises
        ------
        PCControlExecutionError
            If the click fails.
        """

    @abstractmethod
    async def mouse_double_click(self, x: int | None = None, y: int | None = None) -> None:
        """Double-click the primary mouse button.

        Parameters
        ----------
        x : int | None
            Optional x-coordinate.
        y : int | None
            Optional y-coordinate.
        """

    @abstractmethod
    async def mouse_right_click(self, x: int | None = None, y: int | None = None) -> None:
        """Click the secondary (right) mouse button.

        Parameters
        ----------
        x : int | None
            Optional x-coordinate.
        y : int | None
            Optional y-coordinate.
        """

    @abstractmethod
    async def mouse_drag(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration: float = 0.5,
    ) -> None:
        """Drag the mouse from one point to another.

        Parameters
        ----------
        start_x : int
            Starting x-coordinate.
        start_y : int
            Starting y-coordinate.
        end_x : int
            Ending x-coordinate.
        end_y : int
            Ending y-coordinate.
        duration : float
            Drag duration in seconds.
        """

    @abstractmethod
    async def mouse_scroll(self, clicks: int, x: int | None = None, y: int | None = None) -> None:
        """Scroll the mouse wheel.

        Parameters
        ----------
        clicks : int
            Number of scroll clicks (negative = down, positive = up).
        x : int | None
            Optional x-coordinate.
        y : int | None
            Optional y-coordinate.
        """

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------

    @abstractmethod
    async def keyboard_type_text(self, text: str, interval: float = 0.0) -> None:
        """Type a string of text.

        Parameters
        ----------
        text : str
            The text to type.
        interval : float
            Seconds between each key press.
        """

    @abstractmethod
    async def keyboard_press_key(self, key: str) -> None:
        """Press a single key.

        Parameters
        ----------
        key : str
            Key name (e.g. "enter", "escape", "a").
        """

    @abstractmethod
    async def keyboard_hotkey(self, *keys: str) -> None:
        """Press a combination of keys simultaneously.

        Parameters
        ----------
        keys : str
            Key names (e.g. "ctrl", "c").
        """

    # ------------------------------------------------------------------
    # Clipboard
    # ------------------------------------------------------------------

    @abstractmethod
    async def clipboard_get_text(self) -> ClipboardContent:
        """Read text from the system clipboard.

        Returns
        -------
        ClipboardContent
            Clipboard text content.
        """

    @abstractmethod
    async def clipboard_set_text(self, text: str) -> None:
        """Write text to the system clipboard.

        Parameters
        ----------
        text : str
            Text to set.
        """

    @abstractmethod
    async def clipboard_clear(self) -> None:
        """Clear the system clipboard."""

    # ------------------------------------------------------------------
    # Filesystem
    # ------------------------------------------------------------------

    @abstractmethod
    async def filesystem_list_directory(self, path: str) -> list[FileEntry]:
        """List entries in a directory.

        Parameters
        ----------
        path : str
            Directory path.

        Returns
        -------
        list[FileEntry]
            Sorted list of directory entries.

        Raises
        ------
        PCControlExecutionError
            If the path does not exist or is not a directory.
        """

    @abstractmethod
    async def filesystem_read_file(self, path: str, encoding: str = "utf-8") -> str:
        """Read a text file.

        Parameters
        ----------
        path : str
            File path.
        encoding : str
            File encoding.

        Returns
        -------
        str
            File contents.

        Raises
        ------
        PCControlExecutionError
            If the file does not exist or cannot be read.
        """

    @abstractmethod
    async def filesystem_write_file(self, path: str, content: str, encoding: str = "utf-8") -> FileOpResult:
        """Write text to a file.

        Parameters
        ----------
        path : str
            File path.
        content : str
            Content to write.
        encoding : str
            File encoding.
        """

    @abstractmethod
    async def filesystem_delete_file(self, path: str) -> None:
        """Delete a file.

        Parameters
        ----------
        path : str
            File path to delete.
        """

    @abstractmethod
    async def filesystem_create_directory(self, path: str) -> FileOpResult:
        """Create a directory (including parents).

        Parameters
        ----------
        path : str
            Directory path to create.
        """

    @abstractmethod
    async def filesystem_delete_directory(self, path: str, recursive: bool = False) -> None:
        """Delete a directory.

        Parameters
        ----------
        path : str
            Directory path to delete.
        recursive : bool
            Whether to delete recursively.
        """

    # ------------------------------------------------------------------
    # Windows
    # ------------------------------------------------------------------

    @abstractmethod
    async def window_list(self) -> list[WindowInfo]:
        """List all top-level windows.

        Returns
        -------
        list[WindowInfo]
            Window snapshots.
        """

    @abstractmethod
    async def window_get_active(self) -> WindowInfo | None:
        """Get the currently active window.

        Returns
        -------
        WindowInfo | None
            Active window or ``None`` if unavailable.
        """

    @abstractmethod
    async def window_focus(self, handle: int) -> None:
        """Bring a window to the foreground.

        Parameters
        ----------
        handle : int
            Native window handle.
        """

    @abstractmethod
    async def window_minimize(self, handle: int) -> None:
        """Minimise a window.

        Parameters
        ----------
        handle : int
            Native window handle.
        """

    @abstractmethod
    async def window_maximize(self, handle: int) -> None:
        """Maximise a window.

        Parameters
        ----------
        handle : int
            Native window handle.
        """

    @abstractmethod
    async def window_close(self, handle: int) -> None:
        """Close a window.

        Parameters
        ----------
        handle : int
            Native window handle.
        """

    @abstractmethod
    async def window_resize(self, handle: int, width: int, height: int) -> None:
        """Resize a window.

        Parameters
        ----------
        handle : int
            Native window handle.
        width : int
            New width.
        height : int
            New height.
        """

    @abstractmethod
    async def window_move(self, handle: int, x: int, y: int) -> None:
        """Move a window to a position.

        Parameters
        ----------
        handle : int
            Native window handle.
        x : int
            New x-coordinate.
        y : int
            New y-coordinate.
        """

    # ------------------------------------------------------------------
    # Processes
    # ------------------------------------------------------------------

    @abstractmethod
    async def process_list(self) -> list[ProcessInfo]:
        """List running processes.

        Returns
        -------
        list[ProcessInfo]
            Running process snapshots.
        """

    @abstractmethod
    async def process_kill(self, pid: int, force: bool = False) -> None:
        """Terminate a process.

        Parameters
        ----------
        pid : int
            Process identifier.
        force : bool
            Whether to force-kill.
        """

    # ------------------------------------------------------------------
    # Application launcher
    # ------------------------------------------------------------------

    @abstractmethod
    async def launch_application(
        self,
        app_path: str,
        args: tuple[str, ...] = (),
        working_dir: str | None = None,
    ) -> ApplicationLaunchResult:
        """Launch an application.

        Parameters
        ----------
        app_path : str
            Path to the executable.
        args : tuple[str, ...]
            Command-line arguments.
        working_dir : str | None
            Working directory for the process.

        Returns
        -------
        ApplicationLaunchResult
            Launch result with PID.
        """

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------

    @abstractmethod
    async def notification_show(
        self,
        title: str,
        message: str,
        duration: float = 5.0,
    ) -> None:
        """Show a desktop notification.

        Parameters
        ----------
        title : str
            Notification title.
        message : str
            Notification body.
        duration : float
            Display duration in seconds.
        """

    # ------------------------------------------------------------------
    # Power
    # ------------------------------------------------------------------

    @abstractmethod
    async def power_shutdown(self) -> None:
        """Shut down the system."""

    @abstractmethod
    async def power_restart(self) -> None:
        """Restart the system."""

    @abstractmethod
    async def power_sleep(self) -> None:
        """Put the system to sleep."""

    @abstractmethod
    async def power_hibernate(self) -> None:
        """Hibernate the system."""

    @abstractmethod
    async def power_lock(self) -> None:
        """Lock the system (require password to unlock)."""

    # ------------------------------------------------------------------
    # Volume
    # ------------------------------------------------------------------

    @abstractmethod
    async def volume_get(self) -> VolumeInfo:
        """Get the current system volume.

        Returns
        -------
        VolumeInfo
            Volume level and mute state.
        """

    @abstractmethod
    async def volume_set(self, level: float) -> None:
        """Set the system volume.

        Parameters
        ----------
        level : float
            Volume level (0.0 – 1.0).
        """

    @abstractmethod
    async def volume_mute(self, muted: bool) -> None:
        """Mute or unmute the system audio.

        Parameters
        ----------
        muted : bool
            ``True`` to mute, ``False`` to unmute.
        """

    # ------------------------------------------------------------------
    # Screen
    # ------------------------------------------------------------------

    @abstractmethod
    async def screen_get_size(self) -> ScreenSize:
        """Get the primary screen resolution.

        Returns
        -------
        ScreenSize
            Screen dimensions.
        """

    @abstractmethod
    async def screen_capture(
        self,
        region: tuple[int, int, int, int] | None = None,
        save_path: str | None = None,
    ) -> ScreenshotResult:
        """Capture a screenshot.

        Parameters
        ----------
        region : tuple[int, int, int, int] | None
            Capture region ``(left, top, width, height)``. ``None`` for
            full screen.
        save_path : str | None
            Optional path to save the image file.

        Returns
        -------
        ScreenshotResult
            Captured image data.
        """

    @abstractmethod
    async def screen_list_displays(self) -> list[DisplayInfo]:
        """List connected displays.

        Returns
        -------
        list[DisplayInfo]
            Display information for each monitor.
        """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @abstractmethod
    async def close(self) -> None:
        """Release all driver resources.

        Called during ``PCControlManager.async_shutdown()``.
        Implementations must be idempotent.
        """

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Return ``True`` if the adapter can be used.

        A placeholder adapter (e.g. ``LocalPCControlAdapter``) returns
        ``False``; a fully-initialised pyautogui adapter returns
        ``True``.
        """
