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

from backend.modules.pc_control._local_adapter import LocalPCControlAdapter
from backend.modules.pc_control._production_adapter import ProductionPCControlAdapter
from backend.modules.pc_control._types import (
    ApplicationLaunchResult,
    ClipboardContent,
    DisplayInfo,
    FileEntry,
    Point,
    ProcessInfo,
    ScreenshotResult,
    ScreenSize,
    VolumeInfo,
    WindowInfo,
)
from backend.modules.pc_control.pc_control_module import PCControlManager
from backend.modules.pc_control.ports.pc_control_port import PCControlPort

__all__ = [
    "PCControlManager",
    "PCControlPort",
    "LocalPCControlAdapter",
    "ProductionPCControlAdapter",
    "Point",
    "ScreenSize",
    "FileEntry",
    "ProcessInfo",
    "WindowInfo",
    "DisplayInfo",
    "ClipboardContent",
    "VolumeInfo",
    "ScreenshotResult",
    "ApplicationLaunchResult",
]
