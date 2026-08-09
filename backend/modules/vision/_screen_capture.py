"""
ScreenCapture — screen capture implementation using mss and win32gui.

Provides screen capture and window-specific capture capability.
"""

from __future__ import annotations

import asyncio
import logging

from backend.modules.vision._exceptions import (
    VisionLoadError,
    VisionTimeoutError,
)
from backend.modules.vision._types import ImageData

_LOG = logging.getLogger("naira.vision.screen_capture")


def _create_mss():
    """Create an mss instance using the modern API, falling back to legacy."""
    import mss
    # mss >= 10.0 deprecates mss.mss(); prefer mss.MSS() if available
    factory = getattr(mss, "MSS", None) or mss.mss
    return factory()


class ScreenCapture:
    """Real screen capture provider using mss and win32gui."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or _LOG

    async def capture(
        self,
        *,
        timeout: float = 30.0,
        monitor_index: int = 0,
        region: tuple[int, int, int, int] | None = None,
    ) -> ImageData:
        """
        Capture the current screen using mss.
        monitor_index: 0 = all monitors combined, 1 = primary, 2 = secondary, etc.
        region: optional (left, top, width, height) to capture a specific area instead of full screen.
        """
        def _do_capture() -> tuple[bytes, int, int]:
            import io
            import mss
            from PIL import Image as PILImage

            with _create_mss() as sct:
                if region:
                    left, top, width, height = region
                    monitor = {"left": left, "top": top, "width": width, "height": height}
                else:
                    monitor = sct.monitors[monitor_index]

                screenshot = sct.grab(monitor)
                img = PILImage.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

                buffer = io.BytesIO()
                img.save(buffer, format="PNG")
                img_bytes = buffer.getvalue()

                return img_bytes, img.width, img.height

        try:
            img_bytes, width, height = await asyncio.wait_for(
                asyncio.to_thread(_do_capture), timeout=timeout
            )
            return ImageData(
                source_type="screen_capture",
                source_path=None,
                width=width,
                height=height,
                format="png",
                size_bytes=len(img_bytes),
                data=img_bytes,
            )
        except asyncio.TimeoutError:
            raise VisionTimeoutError(context={"operation": "capture_screen"})
        except Exception as exc:
            raise VisionLoadError(
                f"Screen capture failed: {exc}", context={"operation": "capture_screen"}
            ) from exc

    async def capture_window(
        self,
        *,
        app_name: str,
        timeout: float = 30.0,
    ) -> ImageData:
        """
        Capture only a specific application window by title match.
        Uses win32gui to find window bounds, then mss to capture that region.
        """
        def _do_capture() -> tuple[bytes, int, int]:
            import io
            import mss
            import win32gui
            from PIL import Image as PILImage

            target_hwnd = None

            def enum_cb(hwnd, _):
                nonlocal target_hwnd
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd).lower()
                    if app_name.lower() in title:
                        target_hwnd = hwnd
                        return False
                return True

            win32gui.EnumWindows(enum_cb, None)

            if target_hwnd is None:
                raise ValueError(f"Window '{app_name}' not found")

            rect = win32gui.GetWindowRect(target_hwnd)
            left, top, right, bottom = rect
            width, height = right - left, bottom - top

            with _create_mss() as sct:
                monitor = {"left": left, "top": top, "width": width, "height": height}
                screenshot = sct.grab(monitor)
                img = PILImage.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                buffer = io.BytesIO()
                img.save(buffer, format="PNG")
                return buffer.getvalue(), img.width, img.height

        try:
            img_bytes, width, height = await asyncio.wait_for(
                asyncio.to_thread(_do_capture), timeout=timeout
            )
            return ImageData(
                source_type="screen_capture",
                source_path=None,
                width=width,
                height=height,
                format="png",
                size_bytes=len(img_bytes),
                data=img_bytes,
            )
        except asyncio.TimeoutError:
            raise VisionTimeoutError(context={"operation": "capture_window"})
        except Exception as exc:
            raise VisionLoadError(
                f"Window capture failed: {exc}",
                context={"operation": "capture_window", "app_name": app_name},
            ) from exc

    @property
    def is_available(self) -> bool:
        try:
            import mss  # noqa: F401
            return True
        except ImportError:
            return False
