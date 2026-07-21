"""Comprehensive tests for the capability module.

Covers:
- Capability dataclass
- CapabilityMetadata (eager and lazy)
- CapabilityRegistry
- DependencyGraph
- PermissionIntegration
- CapabilityManager (ModuleInterface lifecycle + registration API)
- CapabilityProvider port
"""

from __future__ import annotations

import pytest

from backend.exceptions import ModuleDegradedError
from backend.modules.capability.capability import Capability
from backend.modules.capability.capability_module import CapabilityManager
from backend.modules.capability.dependency_graph import DependencyGraph
from backend.modules.capability.metadata import CapabilityMetadata
from backend.modules.capability.permissions import PermissionIntegration
from backend.modules.capability.ports.capability_provider import (
    CapabilityProvider,
)
from backend.modules.capability.registry import CapabilityRegistry
from backend.types import ModuleInterface

# =========================================================================
# Capability
# =========================================================================


class TestCapability:
    def test_creation_with_minimal_fields(self) -> None:
        cap = Capability(name="browser", version="1.0.0")
        assert cap.name == "browser"
        assert cap.version == "1.0.0"
        assert cap.enabled is True
        assert cap.metadata == CapabilityMetadata()
        assert cap.dependencies == ()
        assert cap.required_permissions == ()

    def test_creation_with_all_fields(self) -> None:
        meta = CapabilityMetadata(description="Test", tags=("ui",))
        cap = Capability(
            name="vision",
            version="2.1.0",
            enabled=False,
            metadata=meta,
            dependencies=("llm", "memory"),
            required_permissions=("camera",),
        )
        assert cap.name == "vision"
        assert cap.version == "2.1.0"
        assert cap.enabled is False
        assert cap.metadata == meta
        assert cap.dependencies == ("llm", "memory")
        assert cap.required_permissions == ("camera",)

    def test_default_enabled(self) -> None:
        cap = Capability(name="voice", version="1.0.0")
        assert cap.enabled is True

    def test_frozen(self) -> None:
        cap = Capability(name="pc_control", version="1.0.0")
        with pytest.raises(AttributeError):
            cap.name = "other"  # type: ignore[misc]

    def test_equality(self) -> None:
        a = Capability(name="memory", version="1.0.0")
        b = Capability(name="memory", version="1.0.0")
        assert a == b

    def test_inequality(self) -> None:
        a = Capability(name="memory", version="1.0.0")
        b = Capability(name="llm", version="1.0.0")
        assert a != b

    def test_hashable(self) -> None:
        caps = {Capability(name="a", version="1"), Capability(name="a", version="1")}
        assert len(caps) == 1


# =========================================================================
# CapabilityMetadata
# =========================================================================


class TestCapabilityMetadata:
    def test_defaults(self) -> None:
        meta = CapabilityMetadata()
        assert meta.description == ""
        assert meta.version == ""
        assert meta.author == ""
        assert meta.tags == ()

    def test_all_fields(self) -> None:
        meta = CapabilityMetadata(
            description="Browser automation",
            version="1.0.0",
            author="naira",
            tags=("browser", "automation"),
        )
        assert meta.description == "Browser automation"
        assert meta.version == "1.0.0"
        assert meta.author == "naira"
        assert meta.tags == ("browser", "automation")

    def test_lazy_creation(self) -> None:
        loader_called = False

        def loader() -> CapabilityMetadata:
            nonlocal loader_called
            loader_called = True
            return CapabilityMetadata(
                description="Lazy loaded",
                version="2.0.0",
                author="plugin",
                tags=("lazy",),
            )

        meta = CapabilityMetadata.lazy(loader)
        assert meta.description == "(lazy)"
        assert loader_called is False

    def test_lazy_resolve(self) -> None:
        def loader() -> CapabilityMetadata:
            return CapabilityMetadata(
                description="Resolved",
                version="1.0.0",
                author="test",
                tags=("resolved",),
            )

        meta = CapabilityMetadata.lazy(loader).resolve()
        assert meta.description == "Resolved"
        assert meta.version == "1.0.0"
        assert meta.author == "test"
        assert meta.tags == ("resolved",)

    def test_resolve_eager_returns_self(self) -> None:
        meta = CapabilityMetadata(description="Eager")
        result = meta.resolve()
        assert result is meta
        assert result.description == "Eager"

    def test_resolve_twice(self) -> None:
        count = 0

        def loader() -> CapabilityMetadata:
            nonlocal count
            count += 1
            return CapabilityMetadata(
                description=f"Call {count}", version="1.0.0"
            )

        meta = CapabilityMetadata.lazy(loader)
        meta.resolve()
        meta.resolve()
        assert count == 1

    def test_frozen(self) -> None:
        meta = CapabilityMetadata(description="test")
        with pytest.raises(AttributeError):
            meta.description = "other"  # type: ignore[misc]


# =========================================================================
# CapabilityRegistry
# =========================================================================


class TestCapabilityRegistry:
    def test_register(self) -> None:
        reg = CapabilityRegistry()
        cap = Capability(name="browser", version="1.0.0")
        reg.register(cap)
        assert reg.count == 1
        assert reg.has("browser")

    def test_register_duplicate_raises(self) -> None:
        reg = CapabilityRegistry()
        reg.register(Capability(name="browser", version="1.0.0"))
        with pytest.raises(ValueError, match="already registered"):
            reg.register(Capability(name="browser", version="2.0.0"))

    def test_unregister(self) -> None:
        reg = CapabilityRegistry()
        cap = Capability(name="browser", version="1.0.0")
        reg.register(cap)
        result = reg.unregister("browser")
        assert result == cap
        assert reg.count == 0

    def test_unregister_nonexistent_raises(self) -> None:
        reg = CapabilityRegistry()
        with pytest.raises(KeyError, match="not found"):
            reg.unregister("nonexistent")

    def test_get(self) -> None:
        reg = CapabilityRegistry()
        cap = Capability(name="browser", version="1.0.0")
        reg.register(cap)
        assert reg.get("browser") == cap

    def test_get_nonexistent(self) -> None:
        reg = CapabilityRegistry()
        assert reg.get("nonexistent") is None

    def test_list(self) -> None:
        reg = CapabilityRegistry()
        caps = [
            Capability(name="a", version="1"),
            Capability(name="b", version="1"),
        ]
        for c in caps:
            reg.register(c)
        result = reg.list()
        assert len(result) == 2
        assert result[0].name == "a"
        assert result[1].name == "b"

    def test_list_returns_copy(self) -> None:
        reg = CapabilityRegistry()
        reg.register(Capability(name="a", version="1"))
        result = reg.list()
        result.clear()
        assert reg.count == 1

    def test_has(self) -> None:
        reg = CapabilityRegistry()
        reg.register(Capability(name="browser", version="1"))
        assert reg.has("browser") is True
        assert reg.has("nonexistent") is False

    def test_set_enabled(self) -> None:
        reg = CapabilityRegistry()
        cap = Capability(name="browser", version="1", enabled=False)
        reg.register(cap)
        updated = reg.set_enabled("browser", True)
        assert updated.enabled is True
        assert reg.is_enabled("browser") is True

    def test_set_enabled_nonexistent_raises(self) -> None:
        reg = CapabilityRegistry()
        with pytest.raises(KeyError):
            reg.set_enabled("nonexistent", True)

    def test_is_enabled_nonexistent_raises(self) -> None:
        reg = CapabilityRegistry()
        with pytest.raises(KeyError):
            reg.is_enabled("nonexistent")

    def test_enabled_set(self) -> None:
        reg = CapabilityRegistry()
        reg.register(Capability(name="a", version="1", enabled=True))
        reg.register(Capability(name="b", version="1", enabled=False))
        reg.register(Capability(name="c", version="1", enabled=True))
        assert reg.enabled_set() == {"a", "c"}

    def test_clear(self) -> None:
        reg = CapabilityRegistry()
        reg.register(Capability(name="a", version="1"))
        reg.register(Capability(name="b", version="1"))
        assert reg.count == 2
        reg.clear()
        assert reg.count == 0


# =========================================================================
# DependencyGraph
# =========================================================================


class TestDependencyGraph:
    def test_add_node(self) -> None:
        g = DependencyGraph()
        g.add_node("browser", ("llm", "memory"))
        assert g.has_node("browser")
        assert g.node_count == 1
        assert g.is_empty is False

    def test_add_duplicate_raises(self) -> None:
        g = DependencyGraph()
        g.add_node("browser", ())
        with pytest.raises(ValueError, match="already exists"):
            g.add_node("browser", ())

    def test_remove_node(self) -> None:
        g = DependencyGraph()
        g.add_node("browser", ("llm",))
        g.add_node("llm", ())
        g.remove_node("browser")
        assert g.has_node("browser") is False
        assert g.node_count == 1

    def test_remove_nonexistent_raises(self) -> None:
        g = DependencyGraph()
        with pytest.raises(KeyError, match="not found"):
            g.remove_node("nonexistent")

    def test_get_dependencies(self) -> None:
        g = DependencyGraph()
        g.add_node("browser", ("llm", "memory"))
        deps = g.get_dependencies("browser")
        assert deps == frozenset({"llm", "memory"})

    def test_get_dependencies_nonexistent_raises(self) -> None:
        g = DependencyGraph()
        with pytest.raises(KeyError):
            g.get_dependencies("nonexistent")

    def test_get_dependents(self) -> None:
        g = DependencyGraph()
        g.add_node("browser", ("llm",))
        g.add_node("vision", ("llm",))
        g.add_node("llm", ())
        deps = g.get_dependents("llm")
        assert deps == frozenset({"browser", "vision"})

    def test_get_dependents_none(self) -> None:
        g = DependencyGraph()
        assert g.get_dependents("nonexistent") == frozenset()

    def test_is_empty(self) -> None:
        g = DependencyGraph()
        assert g.is_empty is True
        g.add_node("browser", ())
        assert g.is_empty is False

    def test_node_count(self) -> None:
        g = DependencyGraph()
        assert g.node_count == 0
        g.add_node("a", ())
        g.add_node("b", ())
        assert g.node_count == 2

    def test_validate_no_errors(self) -> None:
        g = DependencyGraph()
        g.add_node("browser", ("llm",))
        g.add_node("llm", ())
        assert g.validate() == []

    def test_validate_missing_dependency(self) -> None:
        g = DependencyGraph()
        g.add_node("browser", ("missing_module",))
        errors = g.validate()
        assert len(errors) == 1
        assert "missing_module" in errors[0]

    def test_validate_cycle(self) -> None:
        g = DependencyGraph()
        g.add_node("a", ("b",))
        g.add_node("b", ("a",))
        errors = g.validate()
        assert len(errors) >= 1
        assert any("Circular" in e for e in errors)

    def test_validate_self_cycle(self) -> None:
        g = DependencyGraph()
        g.add_node("a", ("a",))
        errors = g.validate()
        assert len(errors) >= 1
        assert any("Circular" in e for e in errors)

    def test_can_enable_no_deps(self) -> None:
        g = DependencyGraph()
        g.add_node("standalone", ())
        ok, missing = g.can_enable("standalone", set())
        assert ok is True
        assert missing == []

    def test_can_enable_satisfied(self) -> None:
        g = DependencyGraph()
        g.add_node("browser", ("llm",))
        ok, missing = g.can_enable("browser", {"llm"})
        assert ok is True
        assert missing == []

    def test_can_enable_unsatisfied(self) -> None:
        g = DependencyGraph()
        g.add_node("browser", ("llm", "memory"))
        ok, missing = g.can_enable("browser", {"llm"})
        assert ok is False
        assert "memory" in missing

    def test_can_enable_nonexistent(self) -> None:
        g = DependencyGraph()
        ok, missing = g.can_enable("nonexistent", set())
        assert ok is True
        assert missing == []

    def test_can_disable_no_dependents(self) -> None:
        g = DependencyGraph()
        g.add_node("standalone", ())
        ok, blocking = g.can_disable("standalone", {"standalone"})
        assert ok is True
        assert blocking == []

    def test_can_disable_with_enabled_dependent(self) -> None:
        g = DependencyGraph()
        g.add_node("llm", ())
        g.add_node("browser", ("llm",))
        ok, blocking = g.can_disable("llm", {"llm", "browser"})
        assert ok is False
        assert "browser" in blocking

    def test_can_disable_dependent_not_enabled(self) -> None:
        g = DependencyGraph()
        g.add_node("llm", ())
        g.add_node("browser", ("llm",))
        ok, blocking = g.can_disable("llm", {"llm"})
        assert ok is True
        assert blocking == []

    def test_topological_sort_simple(self) -> None:
        g = DependencyGraph()
        g.add_node("b", ("a",))
        g.add_node("c", ("b",))
        g.add_node("a", ())
        order = g.topological_sort()
        assert order.index("a") < order.index("b")
        assert order.index("b") < order.index("c")

    def test_topological_sort_cycle_raises(self) -> None:
        g = DependencyGraph()
        g.add_node("a", ("b",))
        g.add_node("b", ("a",))
        with pytest.raises(ValueError, match="Circular"):
            g.topological_sort()

    def test_topological_sort_empty(self) -> None:
        g = DependencyGraph()
        assert g.topological_sort() == []


# =========================================================================
# PermissionIntegration
# =========================================================================


class TestPermissionIntegration:
    def test_lenient_construction(self) -> None:
        pi = PermissionIntegration()
        assert pi.is_lenient is True

    def test_lenient_check_always_true(self) -> None:
        pi = PermissionIntegration()
        assert pi.check_permission("browser", "camera") is True
        assert pi.check_permission("voice", "microphone") is True

    def test_lenient_required_permissions_empty(self) -> None:
        pi = PermissionIntegration()
        result = pi.required_permissions("browser", {"camera", "microphone"})
        assert result == []


# =========================================================================
# CapabilityManager — ModuleInterface lifecycle
# =========================================================================


class TestCapabilityManagerLifecycle:
    @pytest.mark.asyncio
    async def test_initial_state(self) -> None:
        mgr = CapabilityManager()
        assert mgr.degraded is False
        assert mgr.list_capabilities() == []

    @pytest.mark.asyncio
    async def test_async_init(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        assert mgr.degraded is False

    @pytest.mark.asyncio
    async def test_shutdown_clears_state(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        mgr.register(Capability(name="browser", version="1"))
        assert len(mgr.list_capabilities()) == 1
        await mgr.async_shutdown()
        assert mgr.list_capabilities() == []
        assert mgr.degraded is False

    @pytest.mark.asyncio
    async def test_double_shutdown_is_safe(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        await mgr.async_shutdown()
        await mgr.async_shutdown()
        assert mgr.list_capabilities() == []

    @pytest.mark.asyncio
    async def test_degrade_sets_flag(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        mgr.degrade()
        assert mgr.degraded is True

    @pytest.mark.asyncio
    async def test_double_degrade_is_safe(self) -> None:
        mgr = CapabilityManager()
        mgr.degrade()
        mgr.degrade()
        assert mgr.degraded is True

    @pytest.mark.asyncio
    async def test_logger_injection(self) -> None:
        import logging

        logger = logging.getLogger("test.capability")
        mgr = CapabilityManager(logger=logger)
        assert mgr._logger is logger  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_config_injection(self) -> None:
        config = {"key": "value"}
        mgr = CapabilityManager(config=config)
        assert mgr._config is config


# =========================================================================
# CapabilityManager — registration
# =========================================================================


class TestCapabilityManagerRegistration:
    @pytest.mark.asyncio
    async def test_register(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        cap = Capability(name="browser", version="1.0.0")
        mgr.register(cap)
        assert mgr.get_capability("browser") == cap

    @pytest.mark.asyncio
    async def test_register_no_deps_validates(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        cap = Capability(name="standalone", version="1.0.0")
        mgr.register(cap)
        assert mgr.get_capability("standalone") is not None

    @pytest.mark.asyncio
    async def test_register_duplicate_raises(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        mgr.register(Capability(name="browser", version="1"))
        with pytest.raises(ValueError, match="already registered"):
            mgr.register(Capability(name="browser", version="2"))

    @pytest.mark.asyncio
    async def test_register_allows_pending_deps(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        cap = Capability(
            name="browser",
            version="1",
            dependencies=("not_yet_registered",),
        )
        mgr.register(cap)
        assert mgr.get_capability("browser") is not None

    @pytest.mark.asyncio
    async def test_health_reports_cycle(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        mgr.register(Capability(name="a", version="1", dependencies=("b",)))
        mgr.register(Capability(name="b", version="1", dependencies=("a",)))
        status = mgr.get_health_status()
        assert any("Circular" in e for e in status["dependency_errors"])

    @pytest.mark.asyncio
    async def test_register_pending_dep_allowed(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        cap = Capability(
            name="future", version="1", dependencies=("not_yet_here",)
        )
        mgr.register(cap)
        assert mgr.get_capability("future") is cap
        # Dependency validation is deferred to enable-time / health
        errs = mgr.get_health_status()["dependency_errors"]
        assert any("not_yet_here" in e for e in errs)

    @pytest.mark.asyncio
    async def test_unregister(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        cap = Capability(name="browser", version="1")
        mgr.register(cap)
        result = mgr.unregister("browser")
        assert result == cap
        assert mgr.get_capability("browser") is None

    @pytest.mark.asyncio
    async def test_unregister_nonexistent_raises(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        with pytest.raises(KeyError):
            mgr.unregister("nonexistent")

    @pytest.mark.asyncio
    async def test_get_capability(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        cap = Capability(name="vision", version="2")
        mgr.register(cap)
        assert mgr.get_capability("vision") == cap

    @pytest.mark.asyncio
    async def test_get_capability_nonexistent(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        assert mgr.get_capability("nonexistent") is None

    @pytest.mark.asyncio
    async def test_list_capabilities(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        mgr.register(Capability(name="a", version="1"))
        mgr.register(Capability(name="b", version="1"))
        caps = mgr.list_capabilities()
        assert len(caps) == 2
        names = {c.name for c in caps}
        assert names == {"a", "b"}

    @pytest.mark.asyncio
    async def test_register_degraded_raises(self) -> None:
        mgr = CapabilityManager()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            mgr.register(Capability(name="browser", version="1"))

    @pytest.mark.asyncio
    async def test_unregister_degraded_raises(self) -> None:
        mgr = CapabilityManager()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            mgr.unregister("browser")


# =========================================================================
# CapabilityManager — runtime state
# =========================================================================


class TestCapabilityManagerState:
    @pytest.mark.asyncio
    async def test_enable(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        cap = Capability(name="browser", version="1", enabled=False)
        mgr.register(cap)
        mgr.enable("browser")
        assert mgr.is_enabled("browser") is True

    @pytest.mark.asyncio
    async def test_disable(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        mgr.register(Capability(name="browser", version="1"))
        mgr.disable("browser")
        assert mgr.is_enabled("browser") is False

    @pytest.mark.asyncio
    async def test_is_enabled(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        mgr.register(Capability(name="browser", version="1", enabled=True))
        mgr.register(Capability(name="vision", version="1", enabled=False))
        assert mgr.is_enabled("browser") is True
        assert mgr.is_enabled("vision") is False

    @pytest.mark.asyncio
    async def test_is_enabled_nonexistent_raises(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        with pytest.raises(KeyError):
            mgr.is_enabled("nonexistent")

    @pytest.mark.asyncio
    async def test_enable_nonexistent_raises(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        with pytest.raises(KeyError):
            mgr.enable("nonexistent")

    @pytest.mark.asyncio
    async def test_disable_nonexistent_raises(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        with pytest.raises(KeyError):
            mgr.disable("nonexistent")

    @pytest.mark.asyncio
    async def test_enable_validates_dependencies(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        mgr.register(Capability(name="llm", version="1"))
        mgr.register(
            Capability(name="browser", version="1", dependencies=("llm",))
        )
        mgr.enable("llm")
        mgr.enable("browser")
        assert mgr.is_enabled("browser") is True

    @pytest.mark.asyncio
    async def test_enable_rejects_missing_dependency(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        mgr.register(
            Capability(name="browser", version="1", dependencies=("llm",))
        )
        with pytest.raises(ValueError, match="unsatisfied"):
            mgr.enable("browser")

    @pytest.mark.asyncio
    async def test_disable_validates_dependents(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        mgr.register(Capability(name="llm", version="1"))
        mgr.register(
            Capability(name="browser", version="1", dependencies=("llm",))
        )
        mgr.enable("llm")
        mgr.enable("browser")
        with pytest.raises(ValueError, match="dependents"):
            mgr.disable("llm")

    @pytest.mark.asyncio
    async def test_disable_allows_when_no_active_dependents(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        mgr.register(Capability(name="llm", version="1"))
        mgr.register(
            Capability(name="browser", version="1", enabled=False, dependencies=("llm",))
        )
        mgr.enable("llm")
        mgr.disable("llm")
        assert mgr.is_enabled("llm") is False

    @pytest.mark.asyncio
    async def test_enable_degraded_raises(self) -> None:
        mgr = CapabilityManager()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            mgr.enable("browser")

    @pytest.mark.asyncio
    async def test_disable_degraded_raises(self) -> None:
        mgr = CapabilityManager()
        mgr.degrade()
        with pytest.raises(ModuleDegradedError):
            mgr.disable("browser")


# =========================================================================
# CapabilityManager — health
# =========================================================================


class TestCapabilityManagerHealth:
    @pytest.mark.asyncio
    async def test_health_status_initial(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        status = mgr.get_health_status()
        assert status["degraded"] is False
        assert status["capability_count"] == 0
        assert status["enabled_count"] == 0
        assert status["dependency_errors"] == []

    @pytest.mark.asyncio
    async def test_health_status_with_capabilities(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        mgr.register(Capability(name="a", version="1"))
        mgr.register(Capability(name="b", version="1", enabled=False))
        status = mgr.get_health_status()
        assert status["capability_count"] == 2
        assert status["enabled_count"] == 1

    @pytest.mark.asyncio
    async def test_health_status_degraded(self) -> None:
        mgr = CapabilityManager()
        mgr.degrade()
        status = mgr.get_health_status()
        assert status["degraded"] is True
        assert status["capability_count"] == 0

    @pytest.mark.asyncio
    async def test_health_status_dependency_errors(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        mgr.register(
            Capability(name="browser", version="1", dependencies=("missing",))
        )
        status = mgr.get_health_status()
        assert len(status["dependency_errors"]) > 0


# =========================================================================
# CapabilityManager — permission integration
# =========================================================================


class TestCapabilityManagerPermission:
    @pytest.mark.asyncio
    async def test_check_permission_lenient(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        assert mgr.check_permission("browser", "camera") is True

    @pytest.mark.asyncio
    async def test_required_permissions(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        cap = Capability(
            name="vision",
            version="1",
            required_permissions=("camera",),
        )
        mgr.register(cap)
        perms = mgr.required_permissions("vision")
        # Lenient mode returns empty because no checker installed
        assert perms == []

    @pytest.mark.asyncio
    async def test_required_permissions_nonexistent(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        assert mgr.required_permissions("nonexistent") == []


# =========================================================================
# CapabilityManager — dependency graph access
# =========================================================================


class TestCapabilityManagerDependencyGraph:
    @pytest.mark.asyncio
    async def test_get_dependency_graph(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        dg = mgr.get_dependency_graph()
        assert isinstance(dg, DependencyGraph)
        assert dg.is_empty is True

    @pytest.mark.asyncio
    async def test_enabled_set(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        mgr.register(Capability(name="a", version="1"))
        mgr.register(Capability(name="b", version="1", enabled=False))
        assert mgr.get_enabled_set() == {"a"}


# =========================================================================
# CapabilityManager — provider management
# =========================================================================


class TestCapabilityManagerProviders:
    @pytest.mark.asyncio
    async def test_register_provider(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()

        class DummyProvider(CapabilityProvider):
            @property
            def capability(self) -> Capability:
                return Capability(name="browser", version="1")

            async def initialize(self) -> None:
                pass

            async def shutdown(self) -> None:
                pass

            async def health_check(self) -> bool:
                return True

        provider = DummyProvider()
        mgr.register_provider("browser_provider", provider)
        assert mgr.get_provider("browser_provider") is provider
        assert mgr.get_capability("browser") is not None

    @pytest.mark.asyncio
    async def test_unregister_provider(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()

        class DummyProvider(CapabilityProvider):
            @property
            def capability(self) -> Capability:
                return Capability(name="browser", version="1")

            async def initialize(self) -> None:
                pass

            async def shutdown(self) -> None:
                pass

            async def health_check(self) -> bool:
                return True

        provider = DummyProvider()
        mgr.register_provider("bp", provider)
        result = mgr.unregister_provider("bp")
        assert result is provider
        assert mgr.get_provider("bp") is None
        assert mgr.get_capability("browser") is None

    @pytest.mark.asyncio
    async def test_duplicate_provider_raises(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()

        class DummyProvider(CapabilityProvider):
            @property
            def capability(self) -> Capability:
                return Capability(name="browser", version="1")

            async def initialize(self) -> None:
                pass

            async def shutdown(self) -> None:
                pass

            async def health_check(self) -> bool:
                return True

        mgr.register_provider("bp", DummyProvider())
        with pytest.raises(ValueError, match="already registered"):
            mgr.register_provider("bp", DummyProvider())

    @pytest.mark.asyncio
    async def test_unregister_provider_nonexistent_raises(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()
        with pytest.raises(KeyError):
            mgr.unregister_provider("nonexistent")

    @pytest.mark.asyncio
    async def test_list_providers(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()

        class P1(CapabilityProvider):
            @property
            def capability(self) -> Capability:
                return Capability(name="browser", version="1")

            async def initialize(self) -> None:
                pass

            async def shutdown(self) -> None:
                pass

            async def health_check(self) -> bool:
                return True

        class P2(CapabilityProvider):
            @property
            def capability(self) -> Capability:
                return Capability(name="vision", version="1")

            async def initialize(self) -> None:
                pass

            async def shutdown(self) -> None:
                pass

            async def health_check(self) -> bool:
                return True

        mgr.register_provider("p1", P1())
        mgr.register_provider("p2", P2())
        providers = mgr.list_providers()
        assert len(providers) == 2
        assert "p1" in providers
        assert "p2" in providers

    @pytest.mark.asyncio
    async def test_list_providers_returns_copy(self) -> None:
        mgr = CapabilityManager()
        await mgr.async_init()

        class P(CapabilityProvider):
            @property
            def capability(self) -> Capability:
                return Capability(name="test", version="1")

            async def initialize(self) -> None:
                pass

            async def shutdown(self) -> None:
                pass

            async def health_check(self) -> bool:
                return True

        mgr.register_provider("p1", P())
        providers = mgr.list_providers()
        providers.clear()
        assert len(mgr.list_providers()) == 1

    @pytest.mark.asyncio
    async def test_register_provider_degraded_raises(self) -> None:
        mgr = CapabilityManager()
        mgr.degrade()

        class P(CapabilityProvider):
            @property
            def capability(self) -> Capability:
                return Capability(name="test", version="1")

            async def initialize(self) -> None:
                pass

            async def shutdown(self) -> None:
                pass

            async def health_check(self) -> bool:
                return True

        with pytest.raises(ModuleDegradedError):
            mgr.register_provider("p1", P())


# =========================================================================
# CapabilityProvider — port
# =========================================================================


class TestCapabilityProviderPort:
    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError):
            CapabilityProvider()  # type: ignore[abstract]

    @pytest.mark.asyncio
    async def test_concrete_implementation(self) -> None:
        class TestProvider(CapabilityProvider):
            @property
            def capability(self) -> Capability:
                return Capability(name="test", version="1.0.0")

            async def initialize(self) -> None:
                self.initialized = True

            async def shutdown(self) -> None:
                self.shutdown_called = True

            async def health_check(self) -> bool:
                return True

        provider = TestProvider()
        assert isinstance(provider, CapabilityProvider)
        assert provider.capability.name == "test"
        assert provider.capability.version == "1.0.0"
        await provider.initialize()
        assert provider.initialized is True
        health = await provider.health_check()
        assert health is True
        await provider.shutdown()
        assert provider.shutdown_called is True


# =========================================================================
# ModuleInterface protocol conformance
# =========================================================================


class TestModuleInterfaceConformance:
    def test_capability_manager_conforms_to_protocol(self) -> None:
        assert isinstance(CapabilityManager(), ModuleInterface)

    def test_capability_manager_has_required_methods(self) -> None:
        mgr = CapabilityManager()
        assert hasattr(mgr, "async_init")
        assert hasattr(mgr, "async_shutdown")
        assert hasattr(mgr, "degrade")
