"""
Dependency injection container.

21_System_Contracts.md §5 — constructor injection only,
no service locator, no global state.
"""

from __future__ import annotations

import logging


class DuplicateRegistrationError(Exception):
    """Raised when a service is registered under a name already in use."""


class ServiceNotFoundError(Exception):
    """Raised when a requested service is not registered."""


class DIContainer:
    """Simple registry for boot-time service references.

    Modules receive dependencies through constructor injection
    at wiring time — this container merely holds constructed
    instances until they are injected.

    Provides duplicate registration protection and service lookup.
    """

    def __init__(self) -> None:
        self._services: dict[str, object] = {}
        self._logger = logging.getLogger("naira.di")

    def register(self, name: str, instance: object, *, allow_override: bool = False) -> None:
        """Register a service by name.

        Parameters
        ----------
        name : str
            Service name.
        instance : object
            Service instance.
        allow_override : bool
            If ``False`` (default), raises ``DuplicateRegistrationError``
            when a service with the same name already exists.

        Raises
        ------
        DuplicateRegistrationError
            If a service with the same name is already registered and
            ``allow_override`` is ``False``.
        """
        if name in self._services and not allow_override:
            raise DuplicateRegistrationError(
                f"Service already registered: '{name}'"
            )
        self._services[name] = instance
        self._logger.debug("DI registered: %s = %s", name, type(instance).__name__)

    def get(self, name: str) -> object:
        """Retrieve a registered service.

        Raises
        ------
        ServiceNotFoundError
            If the service is not registered.
        """
        if name not in self._services:
            raise ServiceNotFoundError(f"Service not found: '{name}'")
        return self._services[name]

    def has(self, name: str) -> bool:
        """Check if a service is registered."""
        return name in self._services

    def list_services(self) -> list[str]:
        """Return a sorted list of all registered service names."""
        return sorted(self._services)

    def shutdown(self) -> None:
        """Clear all registered services."""
        self._services.clear()
        self._logger.info("DI container cleared.")
