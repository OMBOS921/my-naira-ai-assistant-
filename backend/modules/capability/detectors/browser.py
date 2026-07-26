"""
BrowserDetector — Discovers installed browsers and default OS browser.
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


class BrowserDetector(BaseDetector):
    """Detector for web browsers on local machine."""

    name = "browser_detector"
    category = CapabilityCategory.BROWSER

    # Known browser paths on Windows
    KNOWN_BROWSERS_WIN = {
        "chrome": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(
                r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
            ),
        ],
        "msedge": [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ],
        "firefox": [
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
        ],
        "brave": [
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            os.path.expandvars(
                r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"
            ),
        ],
        "opera": [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Opera\launcher.exe"),
            r"C:\Program Files\Opera\launcher.exe",
        ],
    }

    def detect(self) -> dict[str, CapabilityInfo]:
        results: dict[str, CapabilityInfo] = {}
        now = time.time()

        available_browsers: list[dict[str, str]] = []

        if sys.platform == "win32":
            for browser_key, candidates in self.KNOWN_BROWSERS_WIN.items():
                found_exe = None
                for path in candidates:
                    if os.path.exists(path):
                        found_exe = path
                        break
                if not found_exe:
                    found_exe = shutil.which(browser_key)

                if found_exe:
                    b_info = {"id": browser_key, "path": found_exe}
                    available_browsers.append(b_info)
                    results[f"browser_{browser_key}"] = CapabilityInfo(
                        name=f"browser_{browser_key}",
                        category=CapabilityCategory.BROWSER,
                        status=CapabilityStatus.AVAILABLE,
                        confidence=CapabilityConfidence.VERIFIED,
                        details=b_info,
                        last_updated=now,
                        ttl=300.0,
                    )
        else:
            # POSIX / Linux / macOS fallbacks
            for b_name in ["chrome", "google-chrome", "firefox", "safari", "edge"]:
                exe = shutil.which(b_name)
                if exe:
                    b_key = "chrome" if "chrome" in b_name else b_name
                    b_info = {"id": b_key, "path": exe}
                    available_browsers.append(b_info)
                    results[f"browser_{b_key}"] = CapabilityInfo(
                        name=f"browser_{b_key}",
                        category=CapabilityCategory.BROWSER,
                        status=CapabilityStatus.AVAILABLE,
                        confidence=CapabilityConfidence.VERIFIED,
                        details=b_info,
                        last_updated=now,
                        ttl=300.0,
                    )

        # Detect default browser
        default_browser_name = self._get_default_browser()

        results["default_browser"] = CapabilityInfo(
            name="default_browser",
            category=CapabilityCategory.BROWSER,
            status=(
                CapabilityStatus.AVAILABLE
                if default_browser_name
                else CapabilityStatus.UNKNOWN
            ),
            confidence=CapabilityConfidence.HIGH,
            details={
                "name": default_browser_name or "unknown",
                "available_browsers": available_browsers,
            },
            last_updated=now,
            ttl=300.0,
        )

        return results

    def _get_default_browser(self) -> str | None:
        if sys.platform == "win32":
            try:
                import winreg

                key_path = r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice"
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                    prog_id, _ = winreg.QueryValueEx(key, "ProgId")
                    prog_id_lower = str(prog_id).lower()
                    if "chrome" in prog_id_lower:
                        return "chrome"
                    if "edge" in prog_id_lower or "msedge" in prog_id_lower:
                        return "msedge"
                    if "firefox" in prog_id_lower:
                        return "firefox"
                    if "brave" in prog_id_lower:
                        return "brave"
                    if "opera" in prog_id_lower:
                        return "opera"
                    return str(prog_id)
            except Exception:
                pass
        return None
