"""
SystemDetector — Probes system specs (CPU, RAM, Storage, Battery, Clipboard, Notifications).
"""

from __future__ import annotations

import os
import platform
import sys
import time
from backend.modules.capability.detectors.base import BaseDetector
from backend.modules.capability.models import (
    CapabilityCategory,
    CapabilityConfidence,
    CapabilityInfo,
    CapabilityStatus,
)


class SystemDetector(BaseDetector):
    """Detector for core OS and hardware system resources."""

    name = "system_detector"
    category = CapabilityCategory.SYSTEM

    def detect(self) -> dict[str, CapabilityInfo]:
        results: dict[str, CapabilityInfo] = {}
        now = time.time()

        # 1. CPU
        cpu_info = self._get_cpu_info()
        results["cpu"] = CapabilityInfo(
            name="cpu",
            category=CapabilityCategory.SYSTEM,
            status=CapabilityStatus.AVAILABLE,
            confidence=CapabilityConfidence.VERIFIED,
            details=cpu_info,
            last_updated=now,
            ttl=120.0,
        )

        # 2. RAM
        ram_info = self._get_ram_info()
        results["ram"] = CapabilityInfo(
            name="ram",
            category=CapabilityCategory.SYSTEM,
            status=CapabilityStatus.AVAILABLE,
            confidence=CapabilityConfidence.VERIFIED,
            details=ram_info,
            last_updated=now,
            ttl=30.0,
        )

        # 3. Storage
        storage_info = self._get_storage_info()
        results["storage"] = CapabilityInfo(
            name="storage",
            category=CapabilityCategory.SYSTEM,
            status=CapabilityStatus.AVAILABLE,
            confidence=CapabilityConfidence.VERIFIED,
            details=storage_info,
            last_updated=now,
            ttl=60.0,
        )

        # 4. Battery
        battery_info = self._get_battery_info()
        results["battery"] = CapabilityInfo(
            name="battery",
            category=CapabilityCategory.SYSTEM,
            status=(
                CapabilityStatus.AVAILABLE
                if battery_info.get("present")
                else CapabilityStatus.UNAVAILABLE
            ),
            confidence=CapabilityConfidence.HIGH,
            details=battery_info,
            last_updated=now,
            ttl=15.0,
        )

        # 5. Clipboard Support
        clipboard_supported = self._check_clipboard_support()
        results["clipboard"] = CapabilityInfo(
            name="clipboard",
            category=CapabilityCategory.SYSTEM,
            status=(
                CapabilityStatus.AVAILABLE
                if clipboard_supported
                else CapabilityStatus.UNAVAILABLE
            ),
            confidence=CapabilityConfidence.VERIFIED,
            details={"supported": clipboard_supported},
            last_updated=now,
            ttl=300.0,
        )

        # 6. Notification Support
        notification_supported = self._check_notification_support()
        results["notification"] = CapabilityInfo(
            name="notification",
            category=CapabilityCategory.SYSTEM,
            status=(
                CapabilityStatus.AVAILABLE
                if notification_supported
                else CapabilityStatus.UNAVAILABLE
            ),
            confidence=CapabilityConfidence.HIGH,
            details={"supported": notification_supported},
            last_updated=now,
            ttl=300.0,
        )

        return results

    def _get_cpu_info(self) -> dict[str, Any]:
        return {
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "cores_logical": os.cpu_count() or 1,
            "system": platform.system(),
        }

    def _get_ram_info(self) -> dict[str, Any]:
        # Using psutil if available, otherwise stdlib / sys
        try:
            import psutil

            mem = psutil.virtual_memory()
            return {
                "total_bytes": mem.total,
                "available_bytes": mem.available,
                "percent_used": mem.percent,
            }
        except ImportError:
            # Fallback estimation
            return {
                "total_bytes": 8 * 1024 * 1024 * 1024,
                "estimated": True,
            }

    def _get_storage_info(self) -> dict[str, Any]:
        try:
            import psutil

            drives = []
            for part in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    drives.append(
                        {
                            "device": part.device,
                            "mountpoint": part.mountpoint,
                            "total_bytes": usage.total,
                            "free_bytes": usage.free,
                            "percent_used": usage.percent,
                        }
                    )
                except OSError:
                    continue
            return {"drives": drives}
        except ImportError:
            # Fallback using shutil.disk_usage
            try:
                root_path = "C:\\" if sys.platform == "win32" else "/"
                total, used, free = shutil.disk_usage(root_path)
                return {
                    "drives": [
                        {
                            "mountpoint": root_path,
                            "total_bytes": total,
                            "free_bytes": free,
                        }
                    ]
                }
            except Exception:
                return {"drives": []}

    def _get_battery_info(self) -> dict[str, Any]:
        try:
            import psutil

            battery = psutil.sensors_battery()
            if battery is not None:
                return {
                    "present": True,
                    "percent": battery.percent,
                    "power_plugged": battery.power_plugged,
                    "secs_left": battery.secsleft,
                }
        except ImportError:
            pass

        return {
            "present": False,
            "percent": None,
            "power_plugged": True,
        }

    def _check_clipboard_support(self) -> bool:
        if sys.platform == "win32":
            return True
        try:
            import tkinter

            return True
        except ImportError:
            pass
        return shutil.which("xclip") is not None or shutil.which("xsel") is not None

    def _check_notification_support(self) -> bool:
        if sys.platform == "win32":
            return True
        return shutil.which("notify-send") is not None
