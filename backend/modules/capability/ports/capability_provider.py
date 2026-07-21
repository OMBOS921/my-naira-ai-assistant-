"""
CapabilityProvider — port for capability plugin providers.

20_Dependency_Rules.md §2 — Port/Adapter pattern.
07_Module_Design.md §1.A — future plugin compatibility.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.modules.capability.capability import Capability


class CapabilityProvider(ABC):
    """Port that capability plugins implement to integrate with the
    Capability Manager.

    Each provider exposes a single ``Capability`` descriptor and
    lifecycle methods that the manager calls during boot and shutdown.

    Usage
    -----
    >>> class BrowserProvider(CapabilityProvider):
    ...     @property
    ...     def capability(self) -> Capability:
    ...         return Capability(name="browser", version="1.0.0")
    ...
    ...     async def initialize(self) -> None: ...
    ...     async def shutdown(self) -> None: ...
    ...     async def health_check(self) -> bool:
    ...         return True
    """

    @property
    @abstractmethod
    def capability(self) -> Capability:
        """Return the ``Capability`` descriptor for this provider."""
        ...

    @abstractmethod
    async def initialize(self) -> None:
        """Perform async initialisation for this provider."""
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """Release all resources held by this provider."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Return ``True`` if the provider is operating normally."""
        ...
