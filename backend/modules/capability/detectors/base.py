"""
BaseDetector — Abstract base class for capability detectors.
"""

from __future__ import annotations

import abc
import logging
import sys

from backend.modules.capability.models import CapabilityCategory, CapabilityInfo

_LOG = logging.getLogger("naira.capability.detector")


class BaseDetector(abc.ABC):
    """Abstract base class for capability detection engines."""

    name: str = "base_detector"
    category: CapabilityCategory = CapabilityCategory.SYSTEM

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or _LOG

    def supports_platform(self, platform_name: str | None = None) -> bool:
        """Return True if detector supports current OS platform."""
        _ = platform_name or sys.platform
        return True

    def safe_detect(self) -> dict[str, CapabilityInfo]:
        """Wrap detect() call with exception handling to guarantee system stability."""
        try:
            return self.detect()
        except Exception as exc:
            self.logger.warning(
                "Detector '%s' failed during detection: %s", self.name, exc
            )
            return {}

    @abc.abstractmethod
    def detect(self) -> dict[str, CapabilityInfo]:
        """Execute detection probe and return map of capability_name -> CapabilityInfo."""
        raise NotImplementedError
