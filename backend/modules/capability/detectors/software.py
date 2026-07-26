"""
SoftwareDetector — Scans installed applications and CLI tools.
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from backend.modules.capability.detectors.base import BaseDetector
from backend.modules.capability.models import (
    CapabilityCategory,
    CapabilityConfidence,
    CapabilityInfo,
    CapabilityStatus,
)


class SoftwareDetector(BaseDetector):
    """Detector for installed desktop applications and command line tools."""

    name = "software_detector"
    category = CapabilityCategory.SOFTWARE

    def detect(self) -> dict[str, CapabilityInfo]:
        results: dict[str, CapabilityInfo] = {}
        now = time.time()

        # Known CLI tools to check via PATH
        cli_tools = [
            "git",
            "docker",
            "node",
            "npm",
            "java",
            "python",
            "python3",
            "adb",
            "fastboot",
            "code",
            "ollama",
            "ffmpeg",
            "curl",
        ]

        for tool in cli_tools:
            path = shutil.which(tool)
            if path:
                results[tool] = CapabilityInfo(
                    name=tool,
                    category=CapabilityCategory.SOFTWARE,
                    status=CapabilityStatus.AVAILABLE,
                    confidence=CapabilityConfidence.VERIFIED,
                    details={"executable": path, "type": "cli"},
                    last_updated=now,
                    ttl=600.0,
                )
            else:
                results[tool] = CapabilityInfo(
                    name=tool,
                    category=CapabilityCategory.SOFTWARE,
                    status=CapabilityStatus.UNAVAILABLE,
                    confidence=CapabilityConfidence.HIGH,
                    details={"type": "cli"},
                    last_updated=now,
                    ttl=600.0,
                )

        # Installed GUI Applications (Windows Registry & Standard Directories)
        installed_apps = self._scan_installed_apps()
        for app_key, app_meta in installed_apps.items():
            results[app_key] = CapabilityInfo(
                name=app_key,
                category=CapabilityCategory.SOFTWARE,
                status=CapabilityStatus.AVAILABLE,
                confidence=CapabilityConfidence.VERIFIED,
                details=app_meta,
                last_updated=now,
                ttl=600.0,
            )

        return results

    def _scan_installed_apps(self) -> dict[str, dict[str, str]]:
        apps: dict[str, dict[str, str]] = {}

        if sys.platform == "win32":
            try:
                import winreg

                uninstall_keys = [
                    (
                        winreg.HKEY_LOCAL_MACHINE,
                        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                    ),
                    (
                        winreg.HKEY_LOCAL_MACHINE,
                        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
                    ),
                    (
                        winreg.HKEY_CURRENT_USER,
                        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                    ),
                ]

                for root, path in uninstall_keys:
                    try:
                        key = winreg.OpenKey(root, path)
                    except OSError:
                        continue

                    try:
                        sub_count, _, _ = winreg.QueryInfoKey(key)
                        for i in range(sub_count):
                            try:
                                sub_name = winreg.EnumKey(key, i)
                                sub_key = winreg.OpenKey(key, sub_name)
                                display_name, _ = winreg.QueryValueEx(
                                    sub_key, "DisplayName"
                                )
                                install_location = ""
                                try:
                                    install_location, _ = winreg.QueryValueEx(
                                        sub_key, "InstallLocation"
                                    )
                                except OSError:
                                    pass

                                display_version = ""
                                try:
                                    display_version, _ = winreg.QueryValueEx(
                                        sub_key, "DisplayVersion"
                                    )
                                except OSError:
                                    pass

                                winreg.CloseKey(sub_key)

                                if display_name and isinstance(display_name, str):
                                    clean_key = (
                                        display_name.lower().replace(" ", "_").strip()
                                    )
                                    apps[clean_key] = {
                                        "name": display_name,
                                        "version": str(display_version),
                                        "location": str(install_location),
                                    }
                            except OSError:
                                continue
                    finally:
                        winreg.CloseKey(key)
            except ImportError:
                pass

        # Check standard desktop application paths
        common_paths = [
            (
                "chrome",
                [
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                ],
            ),
            (
                "vscode",
                [
                    r"C:\Program Files\Microsoft VS Code\Code.exe",
                    os.path.expandvars(
                        r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"
                    ),
                ],
            ),
            (
                "notepad",
                [
                    r"C:\Windows\System32\notepad.exe",
                    r"C:\Windows\notepad.exe",
                ],
            ),
        ]

        for app_name, target_paths in common_paths:
            for p in target_paths:
                if os.path.exists(p):
                    apps[app_name] = {
                        "name": app_name.title(),
                        "executable": p,
                        "location": os.path.dirname(p),
                    }
                    break

        return apps
