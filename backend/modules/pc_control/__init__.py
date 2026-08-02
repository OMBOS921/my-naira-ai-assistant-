"""PC Control module — OS automation and system interaction layer.

07_Module_Design.md §2 — Module responsibilities.
21_System_Contracts.md §15 — Tool contracts.

Public API
----------
- ``PCControlManager`` — central PC-control manager
- ``PCControlPort`` — abstract port for pluggable OS automation adapters
- ``LocalPCControlAdapter`` — placeholder adapter
- ``ProductionPCControlAdapter`` — production adapter using real OS libraries
"""

from __future__ import annotations

from backend.modules.pc_control._account_manager import PCAccountManager
from backend.modules.pc_control._local_adapter import LocalPCControlAdapter
from backend.modules.pc_control._production_adapter import ProductionPCControlAdapter
from backend.modules.pc_control._software_manager import PCSoftwareManager
from backend.modules.pc_control._system_settings import PCSystemSettings
from backend.modules.pc_control._types import (
    ApplicationLaunchResult,
    BluetoothDevice,
    ClipboardContent,
    DisplayInfo,
    DisplaySettings,
    FileEntry,
    InstalledPackage,
    PackageOpResult,
    Point,
    ProcessInfo,
    ScreenshotResult,
    ScreenSize,
    UserAccount,
    VolumeInfo,
    WifiNetwork,
    WindowInfo,
)
from backend.modules.pc_control.pc_control_module import PCControlManager
from backend.modules.pc_control.ports.pc_control_port import PCControlPort

__all__ = [
    "PCControlManager",
    "PCControlPort",
    "LocalPCControlAdapter",
    "ProductionPCControlAdapter",
    "PCSystemSettings",
    "PCSoftwareManager",
    "PCAccountManager",
    "Point",
    "ScreenSize",
    "FileEntry",
    "ProcessInfo",
    "WindowInfo",
    "DisplayInfo",
    "DisplaySettings",
    "ClipboardContent",
    "VolumeInfo",
    "ScreenshotResult",
    "ApplicationLaunchResult",
    "WifiNetwork",
    "BluetoothDevice",
    "InstalledPackage",
    "PackageOpResult",
    "UserAccount",
]
