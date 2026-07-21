"""Tests for the dependency injection container (backend/modules/utils/di.py).

21_System_Contracts.md §5 — Constructor injection only, no service locator,
no global state.
"""

from __future__ import annotations

import pytest

from backend.modules.utils.di import DIContainer, DuplicateRegistrationError, ServiceNotFoundError


class TestDIContainer:
    def test_empty_on_creation(self) -> None:
        container = DIContainer()
        assert container._services == {}

    def test_register_and_retrieve(self) -> None:
        container = DIContainer()
        service = object()
        container.register("my_service", service)
        assert container.get("my_service") is service

    def test_register_duplicate_raises(self) -> None:
        container = DIContainer()
        container.register("key", object())
        with pytest.raises(DuplicateRegistrationError):
            container.register("key", object())

    def test_register_overwrite_with_override(self) -> None:
        container = DIContainer()
        container.register("key", object())
        new_val = object()
        container.register("key", new_val, allow_override=True)
        assert container.get("key") is new_val

    def test_get_missing_key_raises_service_not_found(self) -> None:
        container = DIContainer()
        with pytest.raises(ServiceNotFoundError):
            container.get("nonexistent")

    def test_multiple_services(self) -> None:
        container = DIContainer()
        a, b, c = object(), object(), object()
        container.register("a", a)
        container.register("b", b)
        container.register("c", c)
        assert container.get("a") is a
        assert container.get("b") is b
        assert container.get("c") is c

    def test_shutdown_clears_all(self) -> None:
        container = DIContainer()
        container.register("x", object())
        container.register("y", object())
        container.shutdown()
        assert container._services == {}

    def test_shutdown_idempotent(self) -> None:
        container = DIContainer()
        container.shutdown()
        container.shutdown()
        assert container._services == {}

    def test_register_different_types(self) -> None:
        container = DIContainer()
        container.register("string", "hello")
        container.register("int", 42)
        container.register("dict", {"key": "val"})
        assert container.get("string") == "hello"
        assert container.get("int") == 42
        assert container.get("dict") == {"key": "val"}
