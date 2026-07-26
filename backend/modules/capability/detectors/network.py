"""
NetworkDetector — Probes network status and internet connectivity.
"""

from __future__ import annotations

import socket
import time
from backend.modules.capability.detectors.base import BaseDetector
from backend.modules.capability.models import (
    CapabilityCategory,
    CapabilityConfidence,
    CapabilityInfo,
    CapabilityStatus,
)


class NetworkDetector(BaseDetector):
    """Detector for active network interfaces and internet connectivity."""

    name = "network_detector"
    category = CapabilityCategory.NETWORK

    def detect(self) -> dict[str, CapabilityInfo]:
        results: dict[str, CapabilityInfo] = {}
        now = time.time()

        internet_connected, details = self._check_internet()

        results["internet"] = CapabilityInfo(
            name="internet",
            category=CapabilityCategory.NETWORK,
            status=(
                CapabilityStatus.AVAILABLE
                if internet_connected
                else CapabilityStatus.UNAVAILABLE
            ),
            confidence=CapabilityConfidence.VERIFIED,
            details=details,
            last_updated=now,
            ttl=10.0,
        )

        results["network_status"] = CapabilityInfo(
            name="network_status",
            category=CapabilityCategory.NETWORK,
            status=(
                CapabilityStatus.AVAILABLE
                if internet_connected
                else CapabilityStatus.DEGRADED
            ),
            confidence=CapabilityConfidence.HIGH,
            details=details,
            last_updated=now,
            ttl=10.0,
        )

        return results

    def _check_internet(self) -> tuple[bool, dict[str, Any]]:
        targets = [
            ("8.8.8.8", 53),
            ("1.1.1.1", 53),
        ]

        for host, port in targets:
            try:
                start = time.time()
                with socket.create_connection((host, port), timeout=0.5):
                    latency_ms = round((time.time() - start) * 1000, 2)
                    return True, {
                        "connected": True,
                        "verified_target": host,
                        "latency_ms": latency_ms,
                    }
            except (OSError, TimeoutError):
                continue

        return False, {"connected": False, "verified_target": None}
