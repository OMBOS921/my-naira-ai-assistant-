"""
Unit tests for the central CapabilityRegistry, lazy discovery, TTL caching,
event-driven updates, hot-plug support, and query APIs.
"""

from __future__ import annotations

import time
import threading
from unittest.mock import MagicMock, patch
import pytest

from backend.modules.capability import (
    CapabilityManager,
    CapabilityRegistry,
    CapabilityStatus,
    CapabilityCategory,
    CapabilityConfidence,
    CapabilityInfo,
)
from backend.modules.capability.cache import CapabilityCache
from backend.modules.capability.detectors.base import BaseDetector


class DummyDetector(BaseDetector):
    name = "dummy_detector"
    category = CapabilityCategory.SOFTWARE

    def __init__(self, items: dict[str, CapabilityInfo] | None = None):
        super().__init__()
        self.call_count = 0
        self._items = items or {}

    def detect(self) -> dict[str, CapabilityInfo]:
        self.call_count += 1
        return self._items


class ErrorDetector(BaseDetector):
    name = "error_detector"
    category = CapabilityCategory.SYSTEM

    def detect(self) -> dict[str, CapabilityInfo]:
        raise RuntimeError("Simulated detector error")


class MockEventBus:
    def __init__(self):
        self.published = []

    def publish(self, event_name: str, payload: dict):
        self.published.append((event_name, payload))


class TestCapabilityRegistry:
    def test_lazy_discovery(self):
        """Test that detectors are not run until queried."""
        reg = CapabilityRegistry()
        mock_detector = DummyDetector()
        reg.register_detector(mock_detector)

        assert mock_detector.call_count == 0

        # Querying a software capability should trigger discovery
        reg.get_capability_info("git")
        assert mock_detector.call_count > 0

    def test_ttl_caching(self):
        """Test that cached results are returned within TTL and refreshed after expiration."""
        cache = CapabilityCache(default_ttl=1.0)
        info = CapabilityInfo(
            name="test_cap",
            category=CapabilityCategory.SYSTEM,
            status=CapabilityStatus.AVAILABLE,
            last_updated=time.time(),
            ttl=0.2,
        )
        cache.set(info)

        # Valid in cache
        assert cache.get("test_cap") is not None

        # Sleep past TTL
        time.sleep(0.25)
        assert cache.get("test_cap") is None
        assert cache.get("test_cap", allow_stale=True) is not None

    def test_event_driven_updates(self):
        """Test that capability changes publish events to EventBus."""
        event_bus = MockEventBus()
        reg = CapabilityRegistry(event_bus=event_bus)

        reg.register_hotplug_device("usb_mic", CapabilityCategory.PERIPHERAL)

        assert len(event_bus.published) >= 1
        event_names = [e[0] for e in event_bus.published]
        assert "capability.hotplug" in event_names or "capability.changed" in event_names

    def test_hotplug_support(self):
        """Test hot-plug device registration."""
        reg = CapabilityRegistry()
        info = reg.register_hotplug_device(
            name="webcam_v2",
            category=CapabilityCategory.PERIPHERAL,
            details={"resolution": "1080p"},
        )
        assert info.name == "webcam_v2"
        assert info.status == CapabilityStatus.AVAILABLE
        assert reg.get_capability_info("webcam_v2").details["resolution"] == "1080p"

    def test_query_api_methods(self):
        """Test all required query API methods on CapabilityRegistry and CapabilityManager."""
        mgr = CapabilityManager()

        # Mock capabilities in registry cache directly
        now = time.time()
        mgr.registry._cache.set(
            CapabilityInfo(
                name="chrome",
                category=CapabilityCategory.SOFTWARE,
                status=CapabilityStatus.AVAILABLE,
                last_updated=now,
            )
        )
        mgr.registry._cache.set(
            CapabilityInfo(
                name="default_browser",
                category=CapabilityCategory.BROWSER,
                status=CapabilityStatus.AVAILABLE,
                details={"available_browsers": [{"id": "chrome", "path": "/bin/chrome"}]},
                last_updated=now,
            )
        )
        mgr.registry._cache.set(
            CapabilityInfo(
                name="gpu",
                category=CapabilityCategory.HARDWARE,
                status=CapabilityStatus.AVAILABLE,
                details={"count": 1, "gpus": [{"name": "NVIDIA RTX 4090"}]},
                last_updated=now,
            )
        )
        mgr.registry._cache.set(
            CapabilityInfo(
                name="internet",
                category=CapabilityCategory.NETWORK,
                status=CapabilityStatus.AVAILABLE,
                details={"connected": True},
                last_updated=now,
            )
        )
        mgr.registry._cache.set(
            CapabilityInfo(
                name="python",
                category=CapabilityCategory.RUNTIME,
                status=CapabilityStatus.AVAILABLE,
                details={"active_executable": "/usr/bin/python3"},
                last_updated=now,
            )
        )
        mgr.registry._cache.set(
            CapabilityInfo(
                name="adb",
                category=CapabilityCategory.SOFTWARE,
                status=CapabilityStatus.AVAILABLE,
                details={"executable": "/usr/bin/adb"},
                last_updated=now,
            )
        )
        mgr.registry._cache.set(
            CapabilityInfo(
                name="ollama",
                category=CapabilityCategory.AI,
                status=CapabilityStatus.AVAILABLE,
                details={"running": True, "models": ["llama3"]},
                last_updated=now,
            )
        )
        mgr.registry._cache.set(
            CapabilityInfo(
                name="microphones",
                category=CapabilityCategory.PERIPHERAL,
                status=CapabilityStatus.AVAILABLE,
                details={"devices": [{"index": 0, "name": "USB Mic"}]},
                last_updated=now,
            )
        )
        mgr.registry._cache.set(
            CapabilityInfo(
                name="best_llm_provider",
                category=CapabilityCategory.AI,
                status=CapabilityStatus.AVAILABLE,
                details={"provider": "ollama"},
                last_updated=now,
            )
        )

        assert mgr.is_app_installed("chrome") is True
        assert mgr.find_best_browser()["id"] == "chrome"
        assert mgr.has_gpu() is True
        assert mgr.has_internet() is True
        assert mgr.find_python()["active_executable"] == "/usr/bin/python3"
        assert mgr.find_adb()["executable"] == "/usr/bin/adb"
        assert mgr.find_ollama()["running"] is True
        assert len(mgr.find_available_microphones()) == 1
        assert mgr.find_best_llm_provider()["provider"] == "ollama"

    def test_detector_error_resilience(self):
        """Test that a failing detector does not crash the registry query."""
        reg = CapabilityRegistry()
        reg.register_detector(ErrorDetector())

        # Should log warning and return gracefully
        res = reg.query_capabilities(category=CapabilityCategory.SYSTEM)
        assert isinstance(res, list)

    def test_thread_safety(self):
        """Test thread safety under concurrent writes and queries."""
        reg = CapabilityRegistry()
        errors = []

        def worker(idx: int):
            try:
                for i in range(20):
                    reg.register_hotplug_device(
                        f"dev_{idx}_{i}", CapabilityCategory.PERIPHERAL
                    )
                    reg.query_capabilities(category=CapabilityCategory.PERIPHERAL)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
