"""
Vision exception hierarchy.

21_System_Contracts.md §3 — All application exceptions inherit from
``NairaError`` and carry a ``context`` dict.
"""

from __future__ import annotations

from typing import Any

from backend.exceptions import NairaError


class VisionError(NairaError):
    """Base for all vision-module errors."""


class VisionTimeoutError(VisionError):
    """A vision operation exceeded its timeout."""


class VisionLoadError(VisionError):
    """Image loading failed (file not found, bad format, etc.)."""


class VisionProcessingError(VisionError):
    """Image preprocessing or analysis failed."""


class VisionNotImplementedError(VisionError):
    """The operation is not supported by the current adapter.

    Raised by placeholder adapters (e.g. ``LocalVisionAdapter``)
    to signal that the real implementation has not been wired yet.
    """

    def __init__(self, context: dict[str, Any] | None = None) -> None:
        super().__init__(
            "Vision adapter not available — no ML model or capture driver configured",
            context=context,
        )
