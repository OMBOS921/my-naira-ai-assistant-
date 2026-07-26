"""
CapabilityRegistry — Central capability registry for descriptors and real-time local machine capabilities.

07_Module_Design.md §1.A — capability registration and lifecycle.
Single source of truth for local capabilities.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

from backend.modules.capability.capability import Capability
from backend.modules.capability.cache import CapabilityCache
from backend.modules.capability.detectors import (
    AIDetector,
    BaseDetector,
    BrowserDetector,
    GPUDetector,
    NetworkDetector,
    PeripheralDetector,
    RuntimeDetector,
    SoftwareDetector,
    SystemDetector,
)
from backend.modules.capability.models import (
    CapabilityCategory,
    CapabilityConfidence,
    CapabilityInfo,
    CapabilityStatus,
)

_LOG = logging.getLogger("naira.capability.registry")


class CapabilityRegistry:
    """Internal registry storing capability descriptors and real-time local capabilities.

    Provides a real-time, thread-safe, lazy-discovered view of local system capabilities.
    Maintains backwards compatibility with standard Capability descriptors.
    """

    def __init__(self, event_bus: Any | None = None) -> None:
        self._capabilities: dict[str, Capability] = {}
        self._event_bus = event_bus
        self._lock = threading.RLock()
        self._cache = CapabilityCache()

        # Modular detectors
        self._detectors: dict[CapabilityCategory, list[BaseDetector]] = {}
        self._register_default_detectors()

    def _register_default_detectors(self) -> None:
        defaults: list[BaseDetector] = [
            SoftwareDetector(_LOG),
            BrowserDetector(_LOG),
            RuntimeDetector(_LOG),
            AIDetector(_LOG),
            SystemDetector(_LOG),
            PeripheralDetector(_LOG),
            NetworkDetector(_LOG),
            GPUDetector(_LOG),
        ]
        for detector in defaults:
            self.register_detector(detector)

    def register_detector(self, detector: BaseDetector) -> None:
        """Register a custom capability detector plugin."""
        with self._lock:
            cat = detector.category
            if cat not in self._detectors:
                self._detectors[cat] = []
            self._detectors[cat].append(detector)

    # ------------------------------------------------------------------
    # Standard Capability Descriptor Mutation (Backwards Compatibility)
    # ------------------------------------------------------------------

    def register(self, capability: Capability) -> None:
        """Register a capability descriptor."""
        with self._lock:
            name = capability.name
            if name in self._capabilities:
                msg = f"Capability already registered: {name}"
                raise ValueError(msg)
            self._capabilities[name] = capability

    def unregister(self, name: str) -> Capability:
        """Unregister a capability descriptor and return it."""
        with self._lock:
            if name not in self._capabilities:
                msg = f"Capability not found: {name}"
                raise KeyError(msg)
            return self._capabilities.pop(name)

    # ------------------------------------------------------------------
    # Standard Descriptor Query (Backwards Compatibility)
    # ------------------------------------------------------------------

    def get(self, name: str) -> Capability | None:
        """Retrieve a capability descriptor, or None if not found."""
        with self._lock:
            return self._capabilities.get(name)

    def list(self) -> list[Capability]:
        """Return a copy of all registered capability descriptors."""
        with self._lock:
            return list(self._capabilities.values())

    def has(self, name: str) -> bool:
        """Return True if the capability descriptor is registered."""
        with self._lock:
            return name in self._capabilities

    @property
    def count(self) -> int:
        """Return the number of registered capability descriptors."""
        with self._lock:
            return len(self._capabilities)

    # ------------------------------------------------------------------
    # Standard Descriptor State Management (Backwards Compatibility)
    # ------------------------------------------------------------------

    def set_enabled(self, name: str, enabled: bool) -> Capability:
        """Update the enabled state of a capability descriptor."""
        with self._lock:
            cap = self._capabilities.get(name)
            if cap is None:
                msg = f"Capability not found: {name}"
                raise KeyError(msg)
            updated = Capability(
                name=cap.name,
                version=cap.version,
                enabled=enabled,
                metadata=cap.metadata,
                dependencies=cap.dependencies,
                required_permissions=cap.required_permissions,
            )
            self._capabilities[name] = updated
            return updated

    def is_enabled(self, name: str) -> bool:
        """Return the enabled state of a capability descriptor."""
        with self._lock:
            cap = self._capabilities.get(name)
            if cap is None:
                msg = f"Capability not found: {name}"
                raise KeyError(msg)
            return cap.enabled

    def enabled_set(self) -> set[str]:
        """Return the set of currently enabled capability descriptor names."""
        with self._lock:
            return {
                name
                for name, cap in self._capabilities.items()
                if cap.enabled
            }

    def clear(self) -> None:
        """Remove all registered capability descriptors and clear cache."""
        with self._lock:
            self._capabilities.clear()
            self._cache.clear()

    # ------------------------------------------------------------------
    # Real-Time Capability Discovery & Query API
    # ------------------------------------------------------------------

    def get_capability_info(
        self, name: str, force_refresh: bool = False
    ) -> CapabilityInfo | None:
        """Retrieve real-time capability information by name with lazy discovery."""
        with self._lock:
            if not force_refresh:
                cached = self._cache.get(name)
                if cached is not None:
                    return cached

            # Lazy discovery scan across relevant detectors
            self._run_discovery_for_name(name)
            return self._cache.get(name, allow_stale=True)

    def query_capabilities(
        self,
        *,
        category: CapabilityCategory | str | None = None,
        min_confidence: float = 0.0,
        status: CapabilityStatus | None = None,
        force_refresh: bool = False,
    ) -> list[CapabilityInfo]:
        """Query real-time capability records matching filters."""
        with self._lock:
            if force_refresh:
                self.refresh_all()
            else:
                if category is not None:
                    self._ensure_category_discovered(category)
                else:
                    self.refresh_all_if_empty()

            return self._cache.query(
                category=category,
                min_confidence=min_confidence,
                status=status,
                allow_stale=False,
            )

    def refresh_all(self) -> list[CapabilityInfo]:
        """Force immediate discovery refresh across all registered detectors."""
        with self._lock:
            discovered: list[CapabilityInfo] = []
            for cat, detector_list in self._detectors.items():
                for detector in detector_list:
                    items = detector.safe_detect()
                    for name, info in items.items():
                        old_info = self._cache.get(name, allow_stale=True)
                        self._cache.set(info)
                        discovered.append(info)
                        self._emit_capability_change(old_info, info)
            return discovered

    def refresh_all_if_empty(self) -> None:
        """Run lazy discovery if the capability cache is currently empty."""
        with self._lock:
            if not self._cache.get_all(allow_stale=False):
                self.refresh_all()

    def _ensure_category_discovered(self, category: CapabilityCategory | str) -> None:
        cat_enum = (
            category
            if isinstance(category, CapabilityCategory)
            else self._parse_category(category)
        )
        if cat_enum and cat_enum in self._detectors:
            for detector in self._detectors[cat_enum]:
                items = detector.safe_detect()
                for name, info in items.items():
                    old_info = self._cache.get(name, allow_stale=True)
                    self._cache.set(info)
                    self._emit_capability_change(old_info, info)

    def _run_discovery_for_name(self, name: str) -> None:
        # Match name to potential category
        lowered = name.lower()
        if lowered in ("chrome", "msedge", "firefox", "brave", "opera", "default_browser") or lowered.startswith("browser"):
            self._ensure_category_discovered(CapabilityCategory.BROWSER)
        elif lowered in ("python", "node", "java", "docker"):
            self._ensure_category_discovered(CapabilityCategory.RUNTIME)
        elif lowered in ("ollama", "local_ai_runtimes", "best_llm_provider"):
            self._ensure_category_discovered(CapabilityCategory.AI)
        elif lowered in ("gpu",):
            self._ensure_category_discovered(CapabilityCategory.HARDWARE)
        elif lowered in ("cpu", "ram", "storage", "battery", "clipboard", "notification"):
            self._ensure_category_discovered(CapabilityCategory.SYSTEM)
        elif lowered in ("microphones", "speakers", "cameras", "displays"):
            self._ensure_category_discovered(CapabilityCategory.PERIPHERAL)
        elif lowered in ("internet", "network_status"):
            self._ensure_category_discovered(CapabilityCategory.NETWORK)
        else:
            # Fallback to software detector first, then all
            self._ensure_category_discovered(CapabilityCategory.SOFTWARE)
            if not self._cache.get(name):
                self.refresh_all()

    def register_hotplug_device(
        self,
        name: str,
        category: CapabilityCategory | str,
        details: dict[str, Any] | None = None,
        status: CapabilityStatus = CapabilityStatus.AVAILABLE,
    ) -> CapabilityInfo:
        """Support hot-plug devices dynamically added at runtime."""
        with self._lock:
            info = CapabilityInfo(
                name=name,
                category=category,
                status=status,
                confidence=CapabilityConfidence.VERIFIED,
                details=details or {},
                last_updated=time.time(),
                ttl=600.0,
            )
            old_info = self._cache.get(name, allow_stale=True)
            self._cache.set(info)
            self._emit_event(
                "capability.hotplug",
                {
                    "name": name,
                    "category": str(category),
                    "status": status.value,
                    "details": details or {},
                },
            )
            self._emit_capability_change(old_info, info)
            return info

    # ------------------------------------------------------------------
    # Specific Required Query API Methods
    # ------------------------------------------------------------------

    def is_app_installed(self, app_name: str) -> bool:
        """Return True if the specified application is installed."""
        clean_name = app_name.lower().strip()
        info = self.get_capability_info(clean_name)
        if info and info.is_available:
            return True

        # Check in software query
        apps = self.query_capabilities(category=CapabilityCategory.SOFTWARE)
        for app in apps:
            if clean_name in app.name.lower():
                return app.is_available
            app_meta_name = str(app.details.get("name", "")).lower()
            if clean_name in app_meta_name:
                return app.is_available
        return False

    def find_best_browser(self) -> dict[str, Any] | None:
        """Find best available browser with path details."""
        info = self.get_capability_info("default_browser")
        if info and info.details.get("available_browsers"):
            browsers = info.details["available_browsers"]
            if browsers:
                return browsers[0]

        all_browsers = self.query_capabilities(category=CapabilityCategory.BROWSER)
        for b in all_browsers:
            if b.name != "default_browser" and b.is_available:
                return b.details
        return None

    def has_gpu(self) -> bool:
        """Return True if a dedicated GPU is available."""
        info = self.get_capability_info("gpu")
        return bool(info and info.is_available and info.details.get("count", 0) > 0)

    def has_internet(self) -> bool:
        """Return True if internet connectivity is verified."""
        info = self.get_capability_info("internet")
        return bool(info and info.is_available and info.details.get("connected", False))

    def find_python(self) -> dict[str, Any] | None:
        """Find Python installations and current active executable."""
        info = self.get_capability_info("python")
        if info and info.is_available:
            return info.details
        return None

    def find_adb(self) -> dict[str, Any] | None:
        """Find Android Debug Bridge (ADB) installation."""
        info = self.get_capability_info("adb")
        if info and info.is_available:
            return info.details
        return None

    def find_ollama(self) -> dict[str, Any] | None:
        """Find Ollama local AI daemon installation and status."""
        info = self.get_capability_info("ollama")
        if info and info.is_available:
            return info.details
        return None

    def find_available_microphones(self) -> list[dict[str, Any]]:
        """Return list of available microphone input devices."""
        info = self.get_capability_info("microphones")
        if info and info.details:
            return info.details.get("devices", [])
        return []

    def find_best_llm_provider(self) -> dict[str, Any] | None:
        """Evaluate best available local LLM provider."""
        info = self.get_capability_info("best_llm_provider")
        if info and info.is_available:
            return info.details
        return None

    # ------------------------------------------------------------------
    # Internal Helpers & Event Integration
    # ------------------------------------------------------------------

    def _parse_category(self, cat_str: str) -> CapabilityCategory | None:
        try:
            return CapabilityCategory(cat_str.lower())
        except ValueError:
            return None

    def _emit_capability_change(
        self, old_info: CapabilityInfo | None, new_info: CapabilityInfo
    ) -> None:
        if old_info is None or old_info.status != new_info.status:
            self._emit_event(
                "capability.changed",
                {
                    "name": new_info.name,
                    "category": str(new_info.category),
                    "old_status": old_info.status.value if old_info else "none",
                    "new_status": new_info.status.value,
                    "confidence": new_info.confidence,
                },
            )

    def _emit_event(self, event_name: str, payload: dict[str, Any]) -> None:
        if self._event_bus is not None:
            try:
                if hasattr(self._event_bus, "publish"):
                    self._event_bus.publish(event_name, payload)
                elif hasattr(self._event_bus, "emit"):
                    self._event_bus.emit(event_name, payload)
            except Exception as exc:
                _LOG.warning("Failed to emit event '%s': %s", event_name, exc)
