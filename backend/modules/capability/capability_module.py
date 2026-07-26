"""
CapabilityManager — the single public class for the capability module.

07_Module_Design.md §1.A — Capability Manager responsibilities.
21_System_Contracts.md §4.2 — ModuleInterface protocol.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from backend.exceptions import ModuleDegradedError
from backend.modules.capability.capability import Capability
from backend.modules.capability.dependency_graph import DependencyGraph
from backend.modules.capability.permissions import PermissionIntegration
from backend.modules.capability.registry import CapabilityRegistry

if TYPE_CHECKING:
    from backend.modules.capability.ports.capability_provider import (
        CapabilityProvider,
    )

_LOG = logging.getLogger("naira.capability")


class CapabilityManager:
    """Central capability manager — registration, lifecycle, dependency
    validation, and permission integration.

    Conforms to ``ModuleInterface`` (``backend/types.py``).

    Parameters
    ----------
    config : object | None
        Application configuration (``AppConfig`` or compatible).
    logger : logging.Logger | None
        Module-scoped logger.  If ``None``, a default logger is used.
    """

    def __init__(
        self,
        *,
        config: object | None = None,
        logger: logging.Logger | None = None,
        event_bus: object | None = None,
    ) -> None:
        self._config = config
        self._logger = logger or _LOG
        self._event_bus = event_bus
        self._registry = CapabilityRegistry(event_bus=event_bus)
        self._dependency_graph = DependencyGraph()
        self._permissions = PermissionIntegration()
        self._providers: dict[str, CapabilityProvider] = {}
        self._degraded: bool = False

    # ------------------------------------------------------------------
    # Module lifecycle  (ModuleInterface protocol)
    # ------------------------------------------------------------------

    async def async_init(self) -> None:
        """Initialise the capability manager.

        No heavyweight setup required for in-memory operation.
        """
        self._degraded = False
        self._logger.info("Capability manager initialised")

    async def async_shutdown(self) -> None:
        """Release all registered capabilities and shutdown providers."""
        self._registry.clear()
        self._dependency_graph = DependencyGraph()
        self._providers.clear()
        self._degraded = False
        self._logger.info("Capability manager shut down")

    def degrade(self) -> None:
        """Mark the manager as degraded after a non-fatal failure."""
        self._degraded = True
        self._logger.warning("Capability manager marked degraded")

    @property
    def degraded(self) -> bool:
        """Return ``True`` if the manager is in a degraded state."""
        return self._degraded

    # ------------------------------------------------------------------
    # Capability registration
    # ------------------------------------------------------------------

    def register(self, capability: Capability) -> None:
        """Register a capability descriptor.

        The capability is stored with its initial enabled state.
        Dependency validation is deferred to enable-time and health
        checks, allowing capabilities to be registered in any order.

        Parameters
        ----------
        capability : Capability
            Descriptor to register.

        Raises
        ------
        ValueError
            If the capability is already registered.
        ModuleDegradedError
            If the manager is degraded.
        """
        self._ensure_not_degraded()
        name = capability.name

        self._registry.register(capability)

        try:
            self._dependency_graph.add_node(name, capability.dependencies)
        except ValueError:
            self._registry.unregister(name)
            raise

        self._logger.debug("Capability registered: %s v%s", name, capability.version)

    def unregister(self, name: str) -> Capability:
        """Unregister a capability and remove it from the dependency graph.

        Parameters
        ----------
        name : str
            Capability name.

        Returns
        -------
        Capability
            The removed descriptor.

        Raises
        ------
        KeyError
            If the capability is not registered.
        ModuleDegradedError
            If the manager is degraded.
        """
        self._ensure_not_degraded()
        capability = self._registry.unregister(name)
        if self._dependency_graph.has_node(name):
            self._dependency_graph.remove_node(name)
        self._logger.debug("Capability unregistered: %s", name)
        return capability

    def get_capability(self, name: str) -> Capability | None:
        """Retrieve a capability descriptor.

        Returns ``None`` if the capability is not registered.
        """
        return self._registry.get(name)

    def list_capabilities(self) -> list[Capability]:
        """Return a list of all registered capability descriptors."""
        return self._registry.list()

    # ------------------------------------------------------------------
    # Runtime state
    # ------------------------------------------------------------------

    def enable(self, name: str) -> None:
        """Enable a registered capability.

        Validates that all dependencies are already enabled.

        Parameters
        ----------
        name : str
            Capability name.

        Raises
        ------
        KeyError
            If the capability is not registered.
        ValueError
            If dependencies are not satisfied.
        ModuleDegradedError
            If the manager is degraded.
        """
        self._ensure_not_degraded()
        enabled = self._registry.enabled_set()
        ok, missing = self._dependency_graph.can_enable(name, enabled)
        if not ok:
            msg = (
                f"Cannot enable '{name}': unsatisfied dependencies: "
                f"{', '.join(missing)}"
            )
            raise ValueError(msg)

        self._registry.set_enabled(name, True)
        self._logger.info("Capability enabled: %s", name)

    def disable(self, name: str) -> None:
        """Disable a registered capability.

        Validates that no enabled capability depends on this one.

        Parameters
        ----------
        name : str
            Capability name.

        Raises
        ------
        KeyError
            If the capability is not registered.
        ValueError
            If dependent capabilities would be broken.
        ModuleDegradedError
            If the manager is degraded.
        """
        self._ensure_not_degraded()
        enabled = self._registry.enabled_set()
        ok, blocking = self._dependency_graph.can_disable(name, enabled)
        if not ok:
            msg = (
                f"Cannot disable '{name}': enabled dependents: "
                f"{', '.join(blocking)}"
            )
            raise ValueError(msg)

        self._registry.set_enabled(name, False)
        self._logger.info("Capability disabled: %s", name)

    def is_enabled(self, name: str) -> bool:
        """Return whether a capability is enabled.

        Raises ``KeyError`` if the capability is not registered.
        """
        return self._registry.is_enabled(name)

    # ------------------------------------------------------------------
    # Provider management  (future plugin compatibility)
    # ------------------------------------------------------------------

    def register_provider(self, name: str, provider: CapabilityProvider) -> None:
        """Register a capability provider plugin.

        The provider's ``capability`` descriptor is automatically
        registered with the manager.

        Parameters
        ----------
        name : str
            Provider name.
        provider : CapabilityProvider
            Provider instance.

        Raises
        ------
        ValueError
            If a provider with the same name is already registered.
        ModuleDegradedError
            If the manager is degraded.
        """
        self._ensure_not_degraded()
        if name in self._providers:
            msg = f"Provider already registered: {name}"
            raise ValueError(msg)

        cap = provider.capability
        self._registry.register(cap)
        try:
            self._dependency_graph.add_node(cap.name, cap.dependencies)
        except ValueError:
            self._registry.unregister(cap.name)
            raise

        self._providers[name] = provider
        self._logger.debug(
            "Provider registered: %s → capability '%s'",
            name,
            cap.name,
        )

    def unregister_provider(self, name: str) -> CapabilityProvider:
        """Unregister a capability provider.

        The associated capability is also unregistered.

        Parameters
        ----------
        name : str
            Provider name.

        Returns
        -------
        CapabilityProvider
            The removed provider instance.

        Raises
        ------
        KeyError
            If the provider is not registered.
        ModuleDegradedError
            If the manager is degraded.
        """
        self._ensure_not_degraded()
        if name not in self._providers:
            msg = f"Provider not found: {name}"
            raise KeyError(msg)

        provider = self._providers.pop(name)
        cap_name = provider.capability.name
        if self._registry.has(cap_name):
            self._registry.unregister(cap_name)
        if self._dependency_graph.has_node(cap_name):
            self._dependency_graph.remove_node(cap_name)

        self._logger.debug("Provider unregistered: %s", name)
        return provider

    def list_providers(self) -> dict[str, CapabilityProvider]:
        """Return a copy of the provider registry."""
        return dict(self._providers)

    def get_provider(self, name: str) -> CapabilityProvider | None:
        """Retrieve a provider by name, or ``None`` if not found."""
        return self._providers.get(name)

    # ------------------------------------------------------------------
    # Permission integration
    # ------------------------------------------------------------------

    def check_permission(self, capability_name: str, permission: str) -> bool:
        """Check whether a permission is granted for a capability.

        Delegates to the ``PermissionIntegration`` instance.
        """
        return self._permissions.check_permission(capability_name, permission)

    def required_permissions(self, capability_name: str) -> list[str]:
        """Return the list of permissions required by a capability.

        Delegates to the ``PermissionIntegration`` instance using
        the capability's declared required permissions.
        """
        cap = self._registry.get(capability_name)
        if cap is None:
            return []
        return self._permissions.required_permissions(
            capability_name, set(cap.required_permissions)
        )

    # ------------------------------------------------------------------
    # Dependency graph access
    # ------------------------------------------------------------------

    def get_dependency_graph(self) -> DependencyGraph:
        """Return the internal dependency graph instance."""
        return self._dependency_graph

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def get_health_status(self) -> dict[str, Any]:
        """Return a snapshot of the manager's health and state.

        Returns a dictionary with keys:
        - ``degraded`` — whether the manager is degraded
        - ``capability_count`` — number of registered capabilities
        - ``enabled_count`` — number of enabled capabilities
        - ``provider_count`` — number of registered providers
        - ``dependency_errors`` — list of validation errors (if any)
        """
        if self._degraded:
            return {
                "degraded": True,
                "capability_count": 0,
                "enabled_count": 0,
                "provider_count": 0,
                "dependency_errors": ["Manager is degraded"],
            }

        enabled = self._registry.enabled_set()
        deps_errors = self._dependency_graph.validate()

        return {
            "degraded": False,
            "capability_count": self._registry.count,
            "enabled_count": len(enabled),
            "provider_count": len(self._providers),
            "dependency_errors": deps_errors,
        }

    def get_enabled_set(self) -> set[str]:
        """Return the set of currently enabled capability names."""
        return self._registry.enabled_set()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_not_degraded(self) -> None:
        if self._degraded:
            raise ModuleDegradedError(
                "CapabilityManager is degraded",
                context={"module": "capability"},
            )

    # ------------------------------------------------------------------
    # Capability Registry Real-Time Discovery API
    # ------------------------------------------------------------------

    @property
    def registry(self) -> CapabilityRegistry:
        """Return the central internal CapabilityRegistry."""
        return self._registry

    def is_app_installed(self, app_name: str) -> bool:
        """Return True if the specified application is installed."""
        return self._registry.is_app_installed(app_name)

    def find_best_browser(self) -> dict[str, Any] | None:
        """Find best available browser with path details."""
        return self._registry.find_best_browser()

    def has_gpu(self) -> bool:
        """Return True if a dedicated GPU is available."""
        return self._registry.has_gpu()

    def has_internet(self) -> bool:
        """Return True if internet connectivity is verified."""
        return self._registry.has_internet()

    def find_python(self) -> dict[str, Any] | None:
        """Find Python installations and active executable."""
        return self._registry.find_python()

    def find_adb(self) -> dict[str, Any] | None:
        """Find Android Debug Bridge (ADB) installation."""
        return self._registry.find_adb()

    def find_ollama(self) -> dict[str, Any] | None:
        """Find Ollama local AI daemon status."""
        return self._registry.find_ollama()

    def find_available_microphones(self) -> list[dict[str, Any]]:
        """Return list of available microphone input devices."""
        return self._registry.find_available_microphones()

    def find_best_llm_provider(self) -> dict[str, Any] | None:
        """Evaluate best available local LLM provider."""
        return self._registry.find_best_llm_provider()

    def query_capabilities(
        self,
        *,
        category: str | None = None,
        min_confidence: float = 0.0,
        force_refresh: bool = False,
    ) -> list[Any]:
        """Query real-time local capabilities matching criteria."""
        return self._registry.query_capabilities(
            category=category,
            min_confidence=min_confidence,
            force_refresh=force_refresh,
        )

    def get_capability_info(self, name: str) -> Any | None:
        """Retrieve real-time local capability information by name."""
        return self._registry.get_capability_info(name)

    def register_hotplug_device(
        self,
        name: str,
        category: str,
        details: dict[str, Any] | None = None,
    ) -> Any:
        """Register a hot-plug device dynamically added at runtime."""
        return self._registry.register_hotplug_device(name, category, details)

