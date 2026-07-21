"""
CapabilityRegistry — internal registry for capability descriptors.

07_Module_Design.md §1.A — capability registration and lifecycle.
"""

from __future__ import annotations

from backend.modules.capability.capability import Capability


class CapabilityRegistry:
    """Internal registry storing capability descriptors by name.

    Owns the runtime enabled/disabled state for each registered
    capability.
    """

    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = {}

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def register(self, capability: Capability) -> None:
        """Register a capability descriptor.

        Parameters
        ----------
        capability : Capability
            Descriptor to register.

        Raises
        ------
        ValueError
            If a capability with the same name is already registered.
        """
        name = capability.name
        if name in self._capabilities:
            msg = f"Capability already registered: {name}"
            raise ValueError(msg)
        self._capabilities[name] = capability

    def unregister(self, name: str) -> Capability:
        """Unregister a capability and return its descriptor.

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
        """
        if name not in self._capabilities:
            msg = f"Capability not found: {name}"
            raise KeyError(msg)
        return self._capabilities.pop(name)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get(self, name: str) -> Capability | None:
        """Retrieve a capability descriptor, or ``None`` if not found."""
        return self._capabilities.get(name)

    def list(self) -> list[Capability]:
        """Return a copy of all registered capability descriptors."""
        return list(self._capabilities.values())

    def has(self, name: str) -> bool:
        """Return ``True`` if the capability is registered."""
        return name in self._capabilities

    @property
    def count(self) -> int:
        """Return the number of registered capabilities."""
        return len(self._capabilities)

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def set_enabled(self, name: str, enabled: bool) -> Capability:
        """Update the enabled state of a capability.

        Parameters
        ----------
        name : str
            Capability name.
        enabled : bool
            New enabled state.

        Returns
        -------
        Capability
            The updated capability descriptor.

        Raises
        ------
        KeyError
            If the capability is not registered.
        """
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
        """Return the enabled state of a capability.

        Raises ``KeyError`` if the capability is not registered.
        """
        cap = self._capabilities.get(name)
        if cap is None:
            msg = f"Capability not found: {name}"
            raise KeyError(msg)
        return cap.enabled

    def enabled_set(self) -> set[str]:
        """Return the set of currently enabled capability names."""
        return {
            name
            for name, cap in self._capabilities.items()
            if cap.enabled
        }

    def clear(self) -> None:
        """Remove all registered capabilities."""
        self._capabilities.clear()
