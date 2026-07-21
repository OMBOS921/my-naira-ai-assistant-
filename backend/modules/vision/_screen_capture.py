"""
ScreenCapture — screen capture interface placeholder.

Future implementations will integrate MSS, PyAutoGUI, or
Playwright screenshot for cross-platform screen capture.
"""

from __future__ import annotations

import logging

from backend.modules.vision._exceptions import VisionNotImplementedError
from backend.modules.vision._types import ImageData

_LOG = logging.getLogger("naira.vision.screen_capture")


class ScreenCapture:
    """Screen capture placeholder.

    All operations raise ``VisionNotImplementedError``.  Real
    implementations (MSS, PyAutoGUI, Playwright) will be wired
    in Phase 2.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or _LOG

    async def capture(
        self,
        *,
        timeout: float = 30.0,
    ) -> ImageData:
        """Capture the current screen.

        Parameters
        ----------
        timeout : float
            Maximum wait time in seconds.

        Returns
        -------
        ImageData
            Captured screen image data.

        Raises
        ------
        VisionNotImplementedError
            Always raised — no capture driver is configured.
        """
        raise VisionNotImplementedError(context={"operation": "capture_screen"})

    @property
    def is_available(self) -> bool:
        """Return ``True`` if a real capture driver is wired."""
        return False
