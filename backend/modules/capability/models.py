"""
Capability models and status descriptors for local machine capability discovery.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class CapabilityStatus(Enum):
    """Status state for a local capability."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class CapabilityCategory(Enum):
    """Categorization of capabilities."""

    SOFTWARE = "software"
    BROWSER = "browser"
    RUNTIME = "runtime"
    HARDWARE = "hardware"
    PERIPHERAL = "peripheral"
    NETWORK = "network"
    SYSTEM = "system"
    AI = "ai"


class CapabilityConfidence:
    """Standard confidence scores (0.0 to 1.0)."""

    VERIFIED = 1.0
    HIGH = 0.9
    MEDIUM = 0.7
    LOW = 0.4
    NONE = 0.0


@dataclass(frozen=True)
class CapabilityInfo:
    """Real-time information snapshot for a local capability.

    Parameters
    ----------
    name : str
        Unique identifier for the capability (e.g., "chrome", "gpu", "git").
    category : CapabilityCategory | str
        Category classification.
    status : CapabilityStatus
        Current status of the capability.
    confidence : float
        Confidence score between 0.0 and 1.0.
    details : dict[str, Any]
        Structured metadata details (paths, versions, specs, device properties).
    last_updated : float
        Monotonic or UNIX epoch timestamp of last probe update.
    ttl : float
        Time-To-Live in seconds for caching.
    """

    name: str
    category: CapabilityCategory | str
    status: CapabilityStatus = CapabilityStatus.UNKNOWN
    confidence: float = CapabilityConfidence.NONE
    details: dict[str, Any] = field(default_factory=dict)
    last_updated: float = field(default_factory=time.time)
    ttl: float = 300.0

    def is_stale(self, now: float | None = None) -> bool:
        """Return True if the capability cache entry has expired."""
        current = time.time() if now is None else now
        return (current - self.last_updated) >= self.ttl

    @property
    def is_available(self) -> bool:
        """Return True if the capability status is AVAILABLE or DEGRADED."""
        return self.status in (CapabilityStatus.AVAILABLE, CapabilityStatus.DEGRADED)

    def to_dict(self) -> dict[str, Any]:
        """Convert CapabilityInfo to a standard dictionary format."""
        category_str = (
            self.category.value
            if isinstance(self.category, CapabilityCategory)
            else str(self.category)
        )
        return {
            "name": self.name,
            "category": category_str,
            "status": self.status.value,
            "confidence": self.confidence,
            "details": dict(self.details),
            "last_updated": self.last_updated,
            "ttl": self.ttl,
        }
