"""PCControlPort — abstract port for pluggable PC-control adapters.

20_Dependency_Rules.md §2 — Port/Adapter pattern.

Concrete adapters (pyautogui, pynput, psutil, etc.) implement this
ABC so ``PCControlManager`` remains agnostic of the underlying driver.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

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
    # Pro-Level Utilities (Archives, Deep File Ops, System Metrics)
    # ------------------------------------------------------------------

    @abstractmethod
    async def filesystem_zip_directory(self, source_dir: str, output_zip_path: str) -> FileOpResult:
        """Compress a directory into a .zip archive."""

    @abstractmethod
    async def filesystem_extract_archive(self, zip_path: str, extract_to_dir: str) -> FileOpResult:
        """Extract a .zip archive into a target directory."""

    @abstractmethod
    async def filesystem_copy_item(self, source_path: str, dest_path: str) -> FileOpResult:
        """Copy a file or directory tree."""

    @abstractmethod
    async def filesystem_move_item(self, source_path: str, dest_path: str) -> FileOpResult:
        """Move a file or directory."""

    @abstractmethod
    async def get_system_metrics(self) -> SystemMetrics:
        """Retrieve active CPU, RAM, Disk, and Network Port metrics."""

    @abstractmethod
    async def get_open_ports(self) -> list[int]:
        """Retrieve list of active listening network ports."""

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

    # ------------------------------------------------------------------
    # System Settings / Software / Accounts
    # ------------------------------------------------------------------

    # --- Wi-Fi ---
    @abstractmethod
    async def wifi_set_power(self, enabled: bool) -> None:
        """Enable or disable Wi-Fi adapter.

        Parameters
        ----------
        enabled : bool
            ``True`` to enable, ``False`` to disable.

        Raises
        ------
        PCControlExecutionError
            If the operation fails.
        PCControlUnsupportedPlatformError
            If Wi-Fi control is not supported on this platform.
        """

    @abstractmethod
    async def wifi_get_power(self) -> bool:
        """Get Wi-Fi power state.

        Returns
        -------
        bool
            ``True`` if Wi-Fi is enabled, ``False`` otherwise.

        Raises
        ------
        PCControlExecutionError
            If the operation fails.
        PCControlUnsupportedPlatformError
            If Wi-Fi status is not available on this platform.
        """

    @abstractmethod
    async def wifi_list_networks(self) -> list['WifiNetwork']:
        """List available Wi-Fi networks.

        Returns
        -------
        list[WifiNetwork]
            List of detected Wi-Fi networks.

        Raises
        ------
        PCControlExecutionError
            If the scan fails.
        PCControlUnsupportedPlatformError
            If Wi-Fi scanning is not supported on this platform.
        """

    @abstractmethod
    async def wifi_connect(self, ssid: str, password: str | None = None) -> None:
        """Connect to a Wi-Fi network.

        Parameters
        ----------
        ssid : str
            Network SSID.
        password : str | None
            Network password (if required).

        Raises
        ------
        PCControlExecutionError
            If the connection fails.
        PCControlUnsupportedPlatformError
            If Wi-Fi connection is not supported on this platform.
        PCControlPermissionError
            If insufficient privileges to change network settings.
        """

    # --- Bluetooth ---
    @abstractmethod
    async def bluetooth_set_power(self, enabled: bool) -> None:
        """Enable or disable Bluetooth adapter.

        Parameters
        ----------
        enabled : bool
            ``True`` to enable, ``False`` to disable.

        Raises
        ------
        PCControlExecutionError
            If the operation fails.
        PCControlUnsupportedPlatformError
            If Bluetooth control is not supported on this platform.
        """

    @abstractmethod
    async def bluetooth_get_power(self) -> bool:
        """Get Bluetooth power state.

        Returns
        -------
        bool
            ``True`` if Bluetooth is enabled, ``False`` otherwise.

        Raises
        ------
        PCControlExecutionError
            If the operation fails.
        PCControlUnsupportedPlatformError
            If Bluetooth status is not available on this platform.
        """

    @abstractmethod
    async def bluetooth_list_devices(self) -> list['BluetoothDevice']:
        """List discoverable Bluetooth devices.

        Returns
        -------
        list[BluetoothDevice]
            List of discovered Bluetooth devices.

        Raises
        ------
        PCControlExecutionError
            If the scan fails.
        PCControlUnsupportedPlatformError
            If Bluetooth scanning is not supported on this platform.
        """

    @abstractmethod
    async def bluetooth_pair(self, device_address: str, pin: str | None = None) -> None:
        """Pair with a Bluetooth device.

        Parameters
        ----------
        device_address : str
            MAC address or identifier of the device to pair.
        pin : str | None
            PIN code for pairing (if required).

        Raises
        ------
        PCControlExecutionError
            If pairing fails.
        PCControlUnsupportedPlatformError
            If Bluetooth pairing is not supported on this platform.
        PCControlPermissionError
            If insufficient privileges to pair devices.
        """

    # --- Display ---
    @abstractmethod
    async def display_get_brightness(self) -> int:
        """Get display brightness level.

        Returns
        -------
        int
            Brightness level as percentage (0-100).

        Raises
        ------
        PCControlExecutionError
            If the operation fails.
        PCControlUnsupportedPlatformError
            If brightness control is not supported on this platform.
        """

    @abstractmethod
    async def display_set_brightness(self, level: int) -> None:
        """Set display brightness level.

        Parameters
        ----------
        level : int
            Brightness level as percentage (0-100).

        Raises
        ------
        PCControlExecutionError
            If the operation fails.
        PCControlUnsupportedPlatformError
            If brightness control is not supported on this platform.
        PCControlPermissionError
            If insufficient privileges to change display settings.
        """

    @abstractmethod
    async def display_get_resolution(self) -> tuple[int, int]:
        """Get current display resolution.

        Returns
        -------
        tuple[int, int]
            Width and height in pixels.

        Raises
        ------
        PCControlExecutionError
            If the operation fails.
        PCControlUnsupportedPlatformError
            If resolution query is not supported on this platform.
        """

    @abstractmethod
    async def display_set_resolution(self, width: int, height: int) -> None:
        """Set display resolution.

        Parameters
        ----------
        width : int
            Width in pixels.
        height : int
            Height in pixels.

        Raises
        ------
        PCControlExecutionError
            If the operation fails.
        PCControlUnsupportedPlatformError
            If resolution change is not supported on this platform.
        PCControlPermissionError
            If insufficient privileges to change display settings.
        """

    @abstractmethod
    async def display_list_resolutions(self) -> list[tuple[int, int]]:
        """List supported display resolutions.

        Returns
        -------
        list[tuple[int, int]]
            List of supported (width, height) tuples.

        Raises
        ------
        PCControlExecutionError
            If the operation fails.
        PCControlUnsupportedPlatformError
            If resolution enumeration is not supported on this platform.
        """

    @abstractmethod
    async def display_set_night_light(self, enabled: bool) -> None:
        """Enable or disable night light/blue light filter.

        Parameters
        ----------
        enabled : bool
            ``True`` to enable, ``False`` to disable.

        Raises
        ------
        PCControlExecutionError
            If the operation fails.
        PCControlUnsupportedPlatformError
            If night light control is not supported on this platform.
        PCControlPermissionError
            If insufficient privileges to change display settings.
        """

    @abstractmethod
    async def display_get_night_light(self) -> bool:
        """Get night light/blue light filter state.

        Returns
        -------
        bool
            ``True`` if enabled, ``False`` otherwise.

        Raises
        ------
        PCControlExecutionError
            If the operation fails.
        PCControlUnsupportedPlatformError
            If night light status is not available on this platform.
        """

    @abstractmethod
    async def display_set_dark_mode(self, enabled: bool) -> None:
        """Enable or disable dark mode.

        Parameters
        ----------
        enabled : bool
            ``True`` to enable, ``False`` to disable.

        Raises
        ------
        PCControlExecutionError
            If the operation fails.
        PCControlUnsupportedPlatformError
            If dark mode control is not supported on this platform.
        PCControlPermissionError
            If insufficient privileges to change system appearance.
        """

    @abstractmethod
    async def display_get_dark_mode(self) -> bool:
        """Get dark mode state.

        Returns
        -------
        bool
            ``True`` if enabled, ``False`` otherwise.

        Raises
        ------
        PCControlExecutionError
            If the operation fails.
        PCControlUnsupportedPlatformError
            If dark mode status is not available on this platform.
        """

    # --- Power Management ---
    @abstractmethod
    async def power_set_airplane_mode(self, enabled: bool) -> None:
        """Enable or disable airplane mode.

        Parameters
        ----------
        enabled : bool
            ``True`` to enable, ``False`` to disable.

        Raises
        ------
        PCControlExecutionError
            If the operation fails.
        PCControlUnsupportedPlatformError
            If airplane mode control is not supported on this platform.
        PCControlPermissionError
            If insufficient privileges to change network settings.
        """

    @abstractmethod
    async def power_get_airplane_mode(self) -> bool:
        """Get airplane mode state.

        Returns
        -------
        bool
            ``True`` if enabled, ``False`` otherwise.

        Raises
        ------
        PCControlExecutionError
            If the operation fails.
        PCControlUnsupportedPlatformError
            If airplane mode status is not available on this platform.
        """

    @abstractmethod
    async def power_set_do_not_disturb(self, enabled: bool) -> None:
        """Enable or disable do not disturb/focus mode.

        Parameters
        ----------
        enabled : bool
            ``True`` to enable, ``False`` to disable.

        Raises
        ------
        PCControlExecutionError
            If the operation fails.
        PCControlUnsupportedPlatformError
            If do not disturb control is not supported on this platform.
        PCControlPermissionError
            If insufficient privileges to change notification settings.
        """

    @abstractmethod
    async def power_get_do_not_disturb(self) -> bool:
        """Get do not disturb/focus mode state.

        Returns
        -------
        bool
            ``True`` if enabled, ``False`` otherwise.

        Raises
        ------
        PCControlExecutionError
            If the operation fails.
        PCControlUnsupportedPlatformError
            If do not disturb status is not available on this platform.
        """

    # --- Software Management ---
    @abstractmethod
    async def software_list_installed(self) -> list['InstalledPackage']:
        """List installed applications/packages.

        Returns
        -------
        list[InstalledPackage]
            List of installed packages.

        Raises
        ------
        PCControlExecutionError
            If the operation fails.
        """

    @abstractmethod
    async def software_install(self, package: str) -> 'PackageOpResult':
        """Install a software package.

        Parameters
        ----------
        package : str
            Package identifier or name to install.

        Returns
        -------
        PackageOpResult
            Result of the installation operation.

        Raises
        ------
        PCControlExecutionError
            If the installation fails.
        PCControlUnsupportedPlatformError
            If package installation is not supported on this platform.
        PCControlPermissionError
            If insufficient privileges to install software.
        """

    @abstractmethod
    async def software_uninstall(self, package: str) -> 'PackageOpResult':
        """Uninstall a software package.

        Parameters
        ----------
        package : str
            Package identifier or name to uninstall.

        Returns
        -------
        PackageOpResult
            Result of the uninstallation operation.

        Raises
        ------
        PCControlExecutionError
            If the uninstallation fails.
        PCControlUnsupportedPlatformError
            If package uninstallation is not supported on this platform.
        PCControlPermissionError
            If insufficient privileges to uninstall software.
        """

    @abstractmethod
    async def software_check_update(self, package: str) -> bool:
        """Check if updates are available for a package.

        Parameters
        ----------
        package : str
            Package identifier or name to check.

        Returns
        -------
        bool
            ``True`` if an update is available, ``False`` otherwise.

        Raises
        ------
        PCControlExecutionError
            If the check fails.
        PCControlUnsupportedPlatformError
            If update checking is not supported on this platform.
        """

    # --- User Account Management ---
    @abstractmethod
    async def account_list_users(self) -> list['UserAccount']:
        """List local user accounts.

        Returns
        -------
        list[UserAccount]
            List of user accounts.

        Raises
        ------
        PCControlExecutionError
            If the operation fails.
        """

    @abstractmethod
    async def account_get_current_user(self) -> 'UserAccount':
        """Get current logged-in user information.

        Returns
        -------
        UserAccount
            Current user information.

        Raises
        ------
        PCControlExecutionError
            If the operation fails.
        """

    @abstractmethod
    async def account_create_user(self, username: str, password: str | None = None) -> 'UserAccount':
        """Create a new standard local user account.

        Parameters
        ----------
        username : str
            Username for the new account.
        password : str | None
            Initial password (if None, a passwordless account may be created where supported).

        Returns
        -------
        UserAccount
            Information about the created account.

        Raises
        ------
        PCControlExecutionError
            If the account creation fails.
        PCControlUnsupportedPlatformError
            If user account creation is not supported on this platform.
        PCControlPermissionError
            If insufficient privileges to create user accounts.
        """

    @abstractmethod
    async def account_set_enabled(self, username: str, enabled: bool) -> None:
        """Enable or disable a user account.

        Parameters
        ----------
        username : str
            Username of the account to modify.
        enabled : bool
            ``True`` to enable, ``False`` to disable.

        Raises
        ------
        PCControlExecutionError
            If the operation fails.
        PCControlUnsupportedPlatformError
            If account enable/disable is not supported on this platform.
        PCControlPermissionError
            If insufficient privileges to modify user accounts.
        """

    @abstractmethod
    async def account_modify_groups(self, username: str, add: list[str] | None = None, remove: list[str] | None = None) -> None:
        """Add or remove a user from groups.

        Parameters
        ----------
        username : str
            Username of the account to modify.
        add : list[str] | None
            List of group names to add the user to.
        remove : list[str] | None
            List of group names to remove the user from.

        Raises
        ------
        PCControlExecutionError
            If the operation fails.
        PCControlUnsupportedPlatformError
            If group modification is not supported on this platform.
        PCControlPermissionError
            If insufficient privileges to modify user group memberships.
        """
