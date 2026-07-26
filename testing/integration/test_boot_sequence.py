"""Integration tests for the full boot and shutdown sequence.

Covers:
- Full boot (Steps 7–12)
- Dependency injection / Port wiring
- Module lifecycle (async_init, async_shutdown)
- Health checks after boot
- Capability registration from feature flags
- Graceful shutdown (reverse init order)
- Double shutdown safety
- Boot failure handling
- Degraded mode
- Duplicate registration protection
- EventBus injection
- Service lookup
- Boot order verification
- Shutdown order verification
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from backend.boot import (
    boot_core_modules,
    register_system_capabilities,
    shutdown_modules,
    verify_boot_health,
)
from backend.modules.capability import CapabilityManager
from backend.modules.context import ContextManager
from backend.modules.llm import LLMManager
from backend.modules.memory import MemoryManager
from backend.modules.prompt import PromptManager
from backend.modules.settings import AppConfig, FeatureFlags, SettingsManager
from backend.modules.utils.di import DIContainer, DuplicateRegistrationError, ServiceNotFoundError
from backend.orchestrator import EventBus, FSMState, Orchestrator
from backend.types import ModuleInterface

# =========================================================================
# Full boot sequence
# =========================================================================


class TestFullBoot:
    """Verify Step 7–12: all modules initialise and register correctly."""

    @pytest.mark.asyncio
    async def test_boot_all_modules(
        self,
        boot_env: None,
        boot_root: Path,
        boot_config: AppConfig,
        di_container: DIContainer,
        orchestrator: Orchestrator,
        event_bus: EventBus,
    ) -> None:
        di_container.register("env", boot_config)
        di_container.register("config", boot_config)
        di_container.register("event_bus", event_bus)
        di_container.register("orchestrator", orchestrator)

        modules = await boot_core_modules(
            container=di_container,
            orchestrator=orchestrator,
            config=boot_config,
            root_dir=boot_root,
            event_bus=event_bus,
        )

        try:
            expected_modules = {
                "settings", "memory", "analytics", "context", "capability", "skills", "tools",
                "security", "browser", "vision", "voice", "pc_control",
                "coding_agent", "planning", "decision", "llm", "prompt",
                "conversation", "context_intelligence", "runtime",
            }
            assert set(modules.keys()) == expected_modules

            for name, mod in modules.items():
                assert isinstance(mod, ModuleInterface), (
                    f"Module '{name}' does not conform to ModuleInterface"
                )
                assert hasattr(mod, "async_init")
                assert hasattr(mod, "async_shutdown")
                assert hasattr(mod, "degrade")

            assert di_container.get("settings_manager") is modules["settings"]
            assert di_container.get("memory_manager") is modules["memory"]
            assert di_container.get("context_manager") is modules["context"]
            assert di_container.get("capability_manager") is modules["capability"]
            assert di_container.get("skill_manager") is modules["skills"]
            assert di_container.get("tool_manager") is modules["tools"]
            assert di_container.get("security_manager") is modules["security"]
            assert di_container.get("vision_manager") is modules["vision"]
            assert di_container.get("voice_manager") is modules["voice"]
            assert di_container.get("browser_manager") is modules["browser"]
            assert di_container.get("pc_control_manager") is modules["pc_control"]
            assert di_container.get("llm_manager") is modules["llm"]
            assert di_container.get("prompt_manager") is modules["prompt"]
            assert di_container.get("conversation_manager") is modules["conversation"]
            assert di_container.get("context_intelligence_manager") is modules["context_intelligence"]
            assert di_container.get("runtime_manager") is modules["runtime"]

            assert orchestrator.state == FSMState.BOOTING
        finally:
            await shutdown_modules(modules)

    @pytest.mark.asyncio
    async def test_boot_with_feature_flags(
        self,
        boot_env: None,
        boot_features: Path,
        boot_config: AppConfig,
        di_container: DIContainer,
        orchestrator: Orchestrator,
        event_bus: EventBus,
    ) -> None:
        di_container.register("env", boot_config)
        di_container.register("config", boot_config)
        di_container.register("event_bus", event_bus)
        di_container.register("orchestrator", orchestrator)

        modules = await boot_core_modules(
            container=di_container,
            orchestrator=orchestrator,
            config=boot_config,
            root_dir=boot_features,
        )

        try:
            cap_mgr: CapabilityManager = modules["capability"]
            caps = cap_mgr.list_capabilities()
            names = {c.name for c in caps}
            assert "memory" in names
            assert "llm" in names
            assert "vision" in names
            assert "browser" in names
            assert "file_manager" in names
            assert "pc_control" in names
        finally:
            await shutdown_modules(modules)

    @pytest.mark.asyncio
    async def test_memory_port_wired_to_context(
        self,
        boot_env: None,
        boot_root: Path,
        boot_config: AppConfig,
        di_container: DIContainer,
        orchestrator: Orchestrator,
        event_bus: EventBus,
    ) -> None:
        di_container.register("env", boot_config)
        di_container.register("config", boot_config)
        di_container.register("event_bus", event_bus)
        di_container.register("orchestrator", orchestrator)

        modules = await boot_core_modules(
            container=di_container,
            orchestrator=orchestrator,
            config=boot_config,
            root_dir=boot_root,
        )

        try:
            ctx: ContextManager = modules["context"]
            mem: MemoryManager = modules["memory"]
            assert ctx._memory_port is mem.memory_adapter  # type: ignore[attr-defined]
        finally:
            await shutdown_modules(modules)

    @pytest.mark.asyncio
    async def test_boot_all_modules_healthy(
        self,
        boot_env: None,
        boot_root: Path,
        boot_config: AppConfig,
        di_container: DIContainer,
        orchestrator: Orchestrator,
        event_bus: EventBus,
    ) -> None:
        di_container.register("env", boot_config)
        di_container.register("config", boot_config)
        di_container.register("event_bus", event_bus)
        di_container.register("orchestrator", orchestrator)

        modules = await boot_core_modules(
            container=di_container,
            orchestrator=orchestrator,
            config=boot_config,
            root_dir=boot_root,
        )

        try:
            for name, mod in modules.items():
                degraded = getattr(mod, "degraded", None)
                if degraded is not None:
                    assert not degraded, f"Module '{name}' is degraded after boot"
        finally:
            await shutdown_modules(modules)


# =========================================================================
# Shutdown sequence
# =========================================================================


class TestShutdown:
    """Verify shutdown reverses init order and is safe to call twice."""

    @pytest.mark.asyncio
    async def test_shutdown_all_modules(
        self,
        boot_env: None,
        boot_root: Path,
        boot_config: AppConfig,
        di_container: DIContainer,
        orchestrator: Orchestrator,
        event_bus: EventBus,
    ) -> None:
        di_container.register("env", boot_config)
        di_container.register("config", boot_config)
        di_container.register("event_bus", event_bus)
        di_container.register("orchestrator", orchestrator)

        modules = await boot_core_modules(
            container=di_container,
            orchestrator=orchestrator,
            config=boot_config,
            root_dir=boot_root,
        )

        # Shutdown modules explicitly
        await shutdown_modules(modules)

        for name, mod in modules.items():
            degraded = getattr(mod, "degraded", None)
            if degraded is not None:
                assert not degraded, f"Module '{name}' still degraded after shutdown"

    @pytest.mark.asyncio
    async def test_orchestrator_module_init_order(
        self,
        boot_env: None,
        boot_root: Path,
        boot_config: AppConfig,
        di_container: DIContainer,
        orchestrator: Orchestrator,
        event_bus: EventBus,
    ) -> None:
        di_container.register("env", boot_config)
        di_container.register("config", boot_config)
        di_container.register("event_bus", event_bus)
        di_container.register("orchestrator", orchestrator)

        modules = await boot_core_modules(
            container=di_container,
            orchestrator=orchestrator,
            config=boot_config,
            root_dir=boot_root,
        )

        try:
            init_order = orchestrator._module_init_order  # type: ignore[attr-defined]
            expected = [
                "settings", "memory", "analytics", "context", "capability", "tools",
                "security", "integrations", "plugins", "browser", "vision", "voice", "pc_control",
                "coding_agent", "planning", "decision", "llm", "prompt",
                "conversation", "context_intelligence", "autonomous_tasks", "multi_agent", "runtime",
            ]
            assert init_order == expected, f"Expected {expected}, got {init_order}"
        finally:
            await shutdown_modules(modules)
    @pytest.mark.asyncio
    async def test_double_shutdown_is_safe(
        self,
        boot_env: None,
        boot_root: Path,
        boot_config: AppConfig,
        di_container: DIContainer,
        orchestrator: Orchestrator,
        event_bus: EventBus,
    ) -> None:
        di_container.register("env", boot_config)
        di_container.register("config", boot_config)
        di_container.register("event_bus", event_bus)
        di_container.register("orchestrator", orchestrator)

        modules = await boot_core_modules(
            container=di_container,
            orchestrator=orchestrator,
            config=boot_config,
            root_dir=boot_root,
        )

        await shutdown_modules(modules)
        await shutdown_modules(modules)

    @pytest.mark.asyncio
    async def test_orchestrator_shutdown_clears_registry(
        self,
        boot_env: None,
        boot_root: Path,
        boot_config: AppConfig,
        di_container: DIContainer,
        orchestrator: Orchestrator,
        event_bus: EventBus,
    ) -> None:
        di_container.register("env", boot_config)
        di_container.register("config", boot_config)
        di_container.register("event_bus", event_bus)
        di_container.register("orchestrator", orchestrator)

        await boot_core_modules(
            container=di_container,
            orchestrator=orchestrator,
            config=boot_config,
            root_dir=boot_root,
        )

        await orchestrator.shutdown()
        assert orchestrator.state == FSMState.SHUTDOWN


# =========================================================================
# Dependency injection
# =========================================================================


class TestDependencyInjection:
    """Verify DI container contains all expected services."""

    @pytest.mark.asyncio
    async def test_di_container_has_all_services(
        self,
        boot_env: None,
        boot_root: Path,
        boot_config: AppConfig,
        di_container: DIContainer,
        orchestrator: Orchestrator,
        event_bus: EventBus,
    ) -> None:
        di_container.register("env", boot_config)
        di_container.register("config", boot_config)
        di_container.register("event_bus", event_bus)
        di_container.register("orchestrator", orchestrator)

        modules = await boot_core_modules(
            container=di_container,
            orchestrator=orchestrator,
            config=boot_config,
            root_dir=boot_root,
        )

        try:
            services = [
                "settings_manager",
                "memory_manager",
                "context_manager",
                "capability_manager",
                "llm_manager",
                "prompt_manager",
                "conversation_manager",
            ]
            for svc in services:
                assert di_container.get(svc) is not None, f"Missing DI service: {svc}"
        finally:
            await shutdown_modules(modules)


# =========================================================================
# Capability registration
# =========================================================================


class TestCapabilityRegistration:
    """Verify system capabilities are registered according to feature flags."""

    def test_no_feature_flags(self) -> None:
        mgr = CapabilityManager()
        register_system_capabilities(mgr)
        names = {c.name for c in mgr.list_capabilities()}
        assert names == {"memory", "llm"}

    def test_all_features_enabled(self) -> None:
        mgr = CapabilityManager()
        flags = FeatureFlags(
            vision=True,
            voice=True,
            browser=True,
            pc_control=True,
            file_manager=True,
            avatar_3d=True,
            security=True,
        )
        register_system_capabilities(mgr, flags)
        names = {c.name for c in mgr.list_capabilities()}
        expected = {
            "memory", "llm",
            "vision", "voice", "browser",
            "pc_control", "file_manager", "avatar_3d",
            "security",
        }
        assert names == expected

    def test_partial_features(self) -> None:
        mgr = CapabilityManager()
        flags = FeatureFlags(vision=True, browser=True)
        register_system_capabilities(mgr, flags)
        names = {c.name for c in mgr.list_capabilities()}
        assert "vision" in names
        assert "browser" in names
        assert "voice" not in names
        assert "pc_control" not in names

    def test_llm_capability_exists(self) -> None:
        mgr = CapabilityManager()
        register_system_capabilities(mgr)
        cap = mgr.get_capability("llm")
        assert cap is not None
        assert cap.name == "llm"
        assert cap.version == "0.1.0"


# =========================================================================
# Boot failure handling
# =========================================================================


class TestBootFailure:
    """Verify that boot failures are caught and modules are cleaned up."""

    @pytest.mark.asyncio
    async def test_boot_graceful_with_missing_dirs(
        self,
        boot_env: None,
        boot_root: Path,
        di_container: DIContainer,
        orchestrator: Orchestrator,
        event_bus: EventBus,
    ) -> None:
        di_container.register("env", AppConfig())
        di_container.register("config", AppConfig())
        di_container.register("event_bus", event_bus)
        di_container.register("orchestrator", orchestrator)

        modules = await boot_core_modules(
            container=di_container,
            orchestrator=orchestrator,
            config=AppConfig(),
            root_dir=boot_root / "nonexistent",
        )

        try:
            assert "settings" in modules
            assert "memory" in modules
        finally:
            await shutdown_modules(modules)

    @pytest.mark.asyncio
    async def test_boot_failure_rolls_back_partial_init(
        self,
        boot_env: None,
        boot_root: Path,
        di_container: DIContainer,
        orchestrator: Orchestrator,
        event_bus: EventBus,
    ) -> None:
        di_container.register("env", AppConfig())
        di_container.register("config", AppConfig())
        di_container.register("event_bus", event_bus)
        di_container.register("orchestrator", orchestrator)

        with (
            patch.object(
                MemoryManager,
                "async_init",
                AsyncMock(side_effect=RuntimeError("Simulated init failure")),
            ),
            pytest.raises(RuntimeError, match="Simulated init failure"),
        ):
            await boot_core_modules(
                container=di_container,
                orchestrator=orchestrator,
                config=AppConfig(),
                root_dir=boot_root,
            )


# =========================================================================
# Module lifecycle
# =========================================================================


class TestModuleLifecycle:
    """Verify every module correctly implements the lifecycle protocol."""

    @pytest.mark.asyncio
    async def test_all_modules_conform_to_protocol(
        self,
        boot_env: None,
        boot_root: Path,
        boot_config: AppConfig,
        di_container: DIContainer,
        orchestrator: Orchestrator,
        event_bus: EventBus,
    ) -> None:
        di_container.register("env", boot_config)
        di_container.register("config", boot_config)
        di_container.register("event_bus", event_bus)
        di_container.register("orchestrator", orchestrator)

        modules = await boot_core_modules(
            container=di_container,
            orchestrator=orchestrator,
            config=boot_config,
            root_dir=boot_root,
        )

        try:
            for name, mod in modules.items():
                assert isinstance(mod, ModuleInterface), (
                    f"Module '{name}' does not conform to ModuleInterface"
                )
                assert hasattr(mod, "async_init")
                assert hasattr(mod, "async_shutdown")
                assert hasattr(mod, "degrade")
        finally:
            await shutdown_modules(modules)


# =========================================================================
# Isolated module tests
# =========================================================================


class TestIsolatedSettingsManager:
    @pytest.mark.asyncio
    async def test_settings_loads_from_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("NAIRA_GEMINI_API_KEY", "test-key")
        config_dir = tmp_path / "config"
        config_dir.mkdir(parents=True, exist_ok=True)

        mgr = SettingsManager(config_dir=config_dir)
        await mgr.async_init()
        assert mgr.config is not None
        assert mgr.env is not None
        assert mgr.features is not None
        assert not mgr.degraded
        await mgr.async_shutdown()


class TestIsolatedMemoryManager:
    @pytest.mark.asyncio
    async def test_memory_uses_provided_paths(self, tmp_path: Path) -> None:
        db_path = tmp_path / "memory" / "test.db"
        idx_path = tmp_path / "memory" / "test_index.json"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        mgr = MemoryManager(db_path=db_path, index_path=idx_path)
        await mgr.async_init()
        assert mgr.memory_adapter is not None
        assert mgr.vector_index_adapter is not None
        assert not mgr.degraded
        await mgr.async_shutdown()


class TestIsolatedLLMManager:
    @pytest.mark.asyncio
    async def test_llm_init_without_providers_goes_degraded(self) -> None:
        mgr = LLMManager()
        await mgr.async_init()
        assert mgr.degraded
        assert mgr.initialized
        await mgr.async_shutdown()


# =========================================================================
# Boot order verification
# =========================================================================


class TestBootOrder:
    """Verify boot order matches 18_Boot_Sequence.md §2."""

    @pytest.mark.asyncio
    async def test_boot_order_is_correct(
        self,
        boot_env: None,
        boot_root: Path,
        boot_config: AppConfig,
        di_container: DIContainer,
        orchestrator: Orchestrator,
        event_bus: EventBus,
    ) -> None:
        di_container.register("env", boot_config)
        di_container.register("config", boot_config)
        di_container.register("event_bus", event_bus)
        di_container.register("orchestrator", orchestrator)

        modules = await boot_core_modules(
            container=di_container,
            orchestrator=orchestrator,
            config=boot_config,
            root_dir=boot_root,
        )

        try:
            init_order = orchestrator._module_init_order  # type: ignore[attr-defined]
            expected = [
                "settings", "memory", "analytics", "context", "capability", "tools",
                "security", "browser", "vision", "voice", "pc_control",
                "coding_agent", "planning", "decision", "llm", "prompt",
                "conversation", "context_intelligence", "runtime",
            ]
            assert init_order == expected, f"Expected {expected}, got {init_order}"
        finally:
            await shutdown_modules(modules)


# =========================================================================
# Shutdown order verification
# =========================================================================


class TestShutdownOrder:
    """Verify shutdown occurs in exact reverse of boot order."""

    @pytest.mark.asyncio
    async def test_shutdown_order_is_reverse_of_boot(
        self,
        boot_env: None,
        boot_root: Path,
        boot_config: AppConfig,
        di_container: DIContainer,
        orchestrator: Orchestrator,
        event_bus: EventBus,
    ) -> None:
        di_container.register("env", boot_config)
        di_container.register("config", boot_config)
        di_container.register("event_bus", event_bus)
        di_container.register("orchestrator", orchestrator)

        modules = await boot_core_modules(
            container=di_container,
            orchestrator=orchestrator,
            config=boot_config,
            root_dir=boot_root,
        )

        try:
            init_order = orchestrator._module_init_order  # type: ignore[attr-defined]
            expected_boot = [
                "settings", "memory", "analytics", "context", "capability", "skills", "tools",
                "security", "browser", "vision", "voice", "pc_control",
                "coding_agent", "planning", "decision", "llm", "prompt",
                "conversation", "context_intelligence", "runtime",
            ]
            expected_shutdown = list(reversed(expected_boot))
            assert init_order == expected_boot
            assert list(reversed(init_order)) == expected_shutdown
        finally:
            await shutdown_modules(modules)


# =========================================================================
# Degraded mode
# =========================================================================


class TestDegradedMode:
    """Verify system enters degraded mode instead of crashing."""

    @pytest.mark.asyncio
    async def test_llm_manager_starts_degraded_without_providers(
        self,
        boot_env: None,
        boot_root: Path,
        boot_config: AppConfig,
        di_container: DIContainer,
        orchestrator: Orchestrator,
        event_bus: EventBus,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        di_container.register("env", boot_config)
        di_container.register("config", boot_config)
        di_container.register("event_bus", event_bus)
        di_container.register("orchestrator", orchestrator)

        # Simulate no Naira API key so no providers are created
        from backend.modules.settings._env import EnvironmentSnapshot
        monkeypatch.setattr(
            EnvironmentSnapshot,
            "load",
            classmethod(lambda cls, env_file=None: EnvironmentSnapshot(naira_api_key="")),
        )

        modules = await boot_core_modules(
            container=di_container,
            orchestrator=orchestrator,
            config=boot_config,
            root_dir=boot_root,
        )

        try:
            assert modules["llm"].degraded
            assert not modules["settings"].degraded
            assert not modules["memory"].degraded
            assert not modules["context"].degraded
            assert not modules["capability"].degraded
            assert not modules["prompt"].degraded
            assert not modules["conversation"].degraded
        finally:
            await shutdown_modules(modules)

    @pytest.mark.asyncio
    async def test_degraded_module_still_registered_in_di(
        self,
        boot_env: None,
        boot_root: Path,
        boot_config: AppConfig,
        di_container: DIContainer,
        orchestrator: Orchestrator,
        event_bus: EventBus,
    ) -> None:
        di_container.register("env", boot_config)
        di_container.register("config", boot_config)
        di_container.register("event_bus", event_bus)
        di_container.register("orchestrator", orchestrator)

        modules = await boot_core_modules(
            container=di_container,
            orchestrator=orchestrator,
            config=boot_config,
            root_dir=boot_root,
        )

        try:
            assert di_container.has("llm_manager")
            llm_mgr = di_container.get("llm_manager")
            assert llm_mgr is modules["llm"]
        finally:
            await shutdown_modules(modules)


# =========================================================================
# Duplicate registration protection
# =========================================================================


class TestDuplicateRegistration:
    """Verify DIContainer prevents duplicate registrations."""

    def test_duplicate_registration_raises_error(self) -> None:
        container = DIContainer()
        container.register("test_svc", object())
        with pytest.raises(DuplicateRegistrationError, match="already registered"):
            container.register("test_svc", object())

    def test_duplicate_registration_with_override(self) -> None:
        container = DIContainer()
        container.register("test_svc", object())
        container.register("test_svc", object(), allow_override=True)
        assert container.has("test_svc")

    def test_boot_duplicate_registration_detected(self) -> None:
        container = DIContainer()
        container.register("settings_manager", object())
        with pytest.raises(DuplicateRegistrationError):
            container.register("settings_manager", object())


# =========================================================================
# Service lookup
# =========================================================================


class TestServiceLookup:
    """Verify DIContainer service lookup works correctly."""

    def test_has_returns_true_for_registered(self) -> None:
        container = DIContainer()
        container.register("my_svc", object())
        assert container.has("my_svc")

    def test_has_returns_false_for_unregistered(self) -> None:
        container = DIContainer()
        assert not container.has("nonexistent")

    def test_get_raises_for_missing(self) -> None:
        container = DIContainer()
        with pytest.raises(ServiceNotFoundError, match="not found"):
            container.get("nonexistent")

    def test_list_services_returns_sorted(self) -> None:
        container = DIContainer()
        container.register("z_svc", object())
        container.register("a_svc", object())
        container.register("m_svc", object())
        services = container.list_services()
        assert services == ["a_svc", "m_svc", "z_svc"]

    def test_list_services_empty(self) -> None:
        container = DIContainer()
        assert container.list_services() == []


# =========================================================================
# EventBus injection
# =========================================================================


class TestEventBusInjection:
    """Verify all modules receive EventBus via constructor injection."""

    @pytest.mark.asyncio
    async def test_all_modules_have_event_bus(
        self,
        boot_env: None,
        boot_root: Path,
        boot_config: AppConfig,
        di_container: DIContainer,
        orchestrator: Orchestrator,
        event_bus: EventBus,
    ) -> None:
        di_container.register("env", boot_config)
        di_container.register("config", boot_config)
        di_container.register("event_bus", event_bus)
        di_container.register("orchestrator", orchestrator)

        modules = await boot_core_modules(
            container=di_container,
            orchestrator=orchestrator,
            config=boot_config,
            root_dir=boot_root,
            event_bus=event_bus,
        )

        try:
            for name, mod in modules.items():
                eb = getattr(mod, "_event_bus", None)
                assert eb is event_bus, (
                    f"Module '{name}' does not have the injected EventBus"
                )
        finally:
            await shutdown_modules(modules)

    @pytest.mark.asyncio
    async def test_event_bus_injected_without_parameter(
        self,
        boot_env: None,
        boot_root: Path,
        boot_config: AppConfig,
        di_container: DIContainer,
        orchestrator: Orchestrator,
        event_bus: EventBus,
    ) -> None:
        di_container.register("env", boot_config)
        di_container.register("config", boot_config)
        di_container.register("event_bus", event_bus)
        di_container.register("orchestrator", orchestrator)

        modules = await boot_core_modules(
            container=di_container,
            orchestrator=orchestrator,
            config=boot_config,
            root_dir=boot_root,
        )

        try:
            for name, mod in modules.items():
                eb = getattr(mod, "_event_bus", None)
                assert eb is None, (
                    f"Module '{name}' has EventBus when none was passed"
                )
        finally:
            await shutdown_modules(modules)


# =========================================================================
# Health verification
# =========================================================================


class TestHealthVerification:
    """Verify boot health checks work correctly."""

    @pytest.mark.asyncio
    async def test_verify_boot_health_all_healthy(
        self,
        boot_env: None,
        boot_root: Path,
        boot_config: AppConfig,
        di_container: DIContainer,
        orchestrator: Orchestrator,
        event_bus: EventBus,
    ) -> None:
        di_container.register("env", boot_config)
        di_container.register("config", boot_config)
        di_container.register("event_bus", event_bus)
        di_container.register("orchestrator", orchestrator)

        modules = await boot_core_modules(
            container=di_container,
            orchestrator=orchestrator,
            config=boot_config,
            root_dir=boot_root,
        )

        try:
            report = verify_boot_health(modules, di_container)
            assert report["all_healthy"]
            assert report["module_count"] == 19
            assert report["service_count"] >= 19
            assert report["missing_modules"] == []
            assert report["missing_services"] == []
        finally:
            await shutdown_modules(modules)


    def test_verify_health_detects_missing_module(self) -> None:
        container = DIContainer()
        container.register("settings_manager", object())
        container.register("memory_manager", object())
        container.register("context_manager", object())
        container.register("capability_manager", object())
        container.register("tool_manager", object())
        container.register("browser_manager", object())
        container.register("llm_manager", object())
        container.register("prompt_manager", object())
        container.register("conversation_manager", object())

        report = verify_boot_health({}, container)
        assert not report["all_healthy"]
        assert len(report["missing_modules"]) == 16

    def test_verify_health_detects_missing_service(self) -> None:
        container = DIContainer()
        container.register("settings_manager", object())
        container.register("memory_manager", object())

        modules = {
            "settings": object(),
            "memory": object(),
            "context": object(),
            "capability": object(),
            "tools": object(),
            "browser": object(),
            "pc_control": object(),
            "llm": object(),
            "prompt": object(),
            "conversation": object(),
            "runtime": object(),
        }
        report = verify_boot_health(modules, container)
        assert not report["all_healthy"]
        assert len(report["missing_services"]) == 14

    def test_verify_health_detects_degraded_modules(self) -> None:
        container = DIContainer()
        container.register("settings_manager", object())
        container.register("memory_manager", object())
        container.register("context_manager", object())
        container.register("capability_manager", object())
        container.register("tool_manager", object())
        container.register("security_manager", object())
        container.register("vision_manager", object())
        container.register("voice_manager", object())
        container.register("browser_manager", object())
        container.register("pc_control_manager", object())
        container.register("llm_manager", object())
        container.register("prompt_manager", object())
        container.register("conversation_manager", object())
        container.register("runtime_manager", object())
        container.register("coding_agent_manager", object())
        container.register("context_intelligence_manager", object())

        class FakeModule:
            degraded = True

        modules = {name: FakeModule() for name in
                   [
    "settings", "memory", "context", "capability", "tools", "security",
    "browser", "vision", "voice", "pc_control", "coding_agent", "llm",
    "prompt", "conversation", "context_intelligence", "runtime",
]}
        report = verify_boot_health(modules, container)
        assert report["all_healthy"]
        assert len(report["degraded_modules"]) == 16


# =========================================================================
# Failed initialization recovery
# =========================================================================


class TestFailedInitRecovery:
    """Verify system handles failed initialization gracefully."""

    @pytest.mark.asyncio
    async def test_memory_init_failure_goes_degraded(
        self,
        tmp_path: Path,
    ) -> None:
        mgr = MemoryManager(
            db_path=tmp_path / "nonexistent_dir" / "test.db",
            index_path=tmp_path / "test_index.json",
        )
        await mgr.async_init()
        assert mgr.degraded
        await mgr.async_shutdown()

    @pytest.mark.asyncio
    async def test_prompt_init_fallback_to_builtin(
        self,
        tmp_path: Path,
    ) -> None:
        mgr = PromptManager(templates_dir=tmp_path / "nonexistent")
        await mgr.async_init()
        assert not mgr.degraded
        assert mgr.get_template_source() == "built-in"
        await mgr.async_shutdown()


# =========================================================================
# Full integration: boot + health + shutdown
# =========================================================================


class TestFullIntegration:
    """End-to-end boot, health check, and shutdown."""

    @pytest.mark.asyncio
    async def test_full_boot_health_shutdown_cycle(
        self,
        boot_env: None,
        boot_root: Path,
        boot_config: AppConfig,
        di_container: DIContainer,
        orchestrator: Orchestrator,
        event_bus: EventBus,
    ) -> None:
        di_container.register("env", boot_config)
        di_container.register("config", boot_config)
        di_container.register("event_bus", event_bus)
        di_container.register("orchestrator", orchestrator)

        modules = await boot_core_modules(
            container=di_container,
            orchestrator=orchestrator,
            config=boot_config,
            root_dir=boot_root,
            event_bus=event_bus,
        )

        try:
            report = verify_boot_health(modules, di_container)
            assert report["all_healthy"]
            assert report["module_count"] == 19
            assert report["service_count"] >= 19

            for svc in ["settings_manager", "memory_manager", "context_manager",
                        "capability_manager", "tool_manager", "security_manager",
                        "vision_manager", "voice_manager", "browser_manager",
                        "pc_control_manager", "coding_agent_manager",
                        "llm_manager", "prompt_manager",
                        "conversation_manager", "context_intelligence_manager",
                        "runtime_manager"]:
                assert di_container.has(svc)
                assert di_container.get(svc) is not None
        finally:
            await shutdown_modules(modules)

    @pytest.mark.asyncio
    async def test_shutdown_clears_degraded_flag(
        self,
        boot_env: None,
        boot_root: Path,
        boot_config: AppConfig,
        di_container: DIContainer,
        orchestrator: Orchestrator,
        event_bus: EventBus,
    ) -> None:
        di_container.register("env", boot_config)
        di_container.register("config", boot_config)
        di_container.register("event_bus", event_bus)
        di_container.register("orchestrator", orchestrator)

        modules = await boot_core_modules(
            container=di_container,
            orchestrator=orchestrator,
            config=boot_config,
            root_dir=boot_root,
        )

        await shutdown_modules(modules)

        for name, mod in modules.items():
            degraded = getattr(mod, "degraded", None)
            if degraded is not None:
                assert not degraded, f"Module '{name}' still degraded after shutdown"


# =========================================================================
# Adapter selection and runtime wiring
# =========================================================================


class TestAdapterSelection:
    """Verify production adapters are selected when deps available,
    and local adapters fall back gracefully."""

    @pytest.mark.asyncio
    async def test_browser_uses_local_adapter_when_playwright_missing(
        self,
        boot_env: None,
        boot_root: Path,
        boot_config: AppConfig,
        di_container: DIContainer,
        orchestrator: Orchestrator,
        event_bus: EventBus,
    ) -> None:
        """When playwright is not installed, BrowserManager should
        select LocalBrowserAdapter."""
        di_container.register("env", boot_config)
        di_container.register("config", boot_config)
        di_container.register("event_bus", event_bus)
        di_container.register("orchestrator", orchestrator)

        modules = await boot_core_modules(
            container=di_container,
            orchestrator=orchestrator,
            config=boot_config,
            root_dir=boot_root,
        )

        try:
            browser = modules["browser"]
            adapter = browser._adapter  # type: ignore[attr-defined]
            adapter_name = type(adapter).__name__
            assert not browser.is_available, \
                f"Browser should not be available with {adapter_name}"
        finally:
            await shutdown_modules(modules)

    @pytest.mark.asyncio
    async def test_pc_control_uses_local_adapter_when_deps_missing(
        self,
        boot_env: None,
        boot_root: Path,
        boot_config: AppConfig,
        di_container: DIContainer,
        orchestrator: Orchestrator,
        event_bus: EventBus,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When pc_control is enabled but no OS libs are installed,
        PCControlManager should use LocalPCControlAdapter."""
        from backend.modules.settings._config import build_app_config

        # Simulate missing dependencies
        import backend.boot as boot_mod
        monkeypatch.setattr(boot_mod, "_PC_HAS_PYAUTOGUI", False)
        monkeypatch.setattr(boot_mod, "_PC_HAS_PSUTIL", False)
        monkeypatch.setattr(boot_mod, "_PC_HAS_PYWIN32", False)

        raw = {
            "pc_control": {"enabled": True},
        }
        custom_config = build_app_config(raw)

        di_container.register("env", custom_config)
        di_container.register("config", custom_config)
        di_container.register("event_bus", event_bus)
        di_container.register("orchestrator", orchestrator)

        modules = await boot_core_modules(
            container=di_container,
            orchestrator=orchestrator,
            config=custom_config,
            root_dir=boot_root,
        )

        try:
            pc = modules["pc_control"]
            adapter = pc._adapter  # type: ignore[attr-defined]
            adapter_name = type(adapter).__name__
            assert "Local" in adapter_name, \
                f"Expected LocalPCControlAdapter but got {adapter_name}"
            assert not pc.is_available, \
                "PC control should not be available without OS libs"
        finally:
            await shutdown_modules(modules)

    @pytest.mark.asyncio
    async def test_llm_starts_healthy_when_api_key_available(
        self,
        boot_env: None,
        boot_root: Path,
        boot_config: AppConfig,
        di_container: DIContainer,
        orchestrator: Orchestrator,
        event_bus: EventBus,
    ) -> None:
        """When NAIRA_API_KEY is set, LLM should be healthy."""
        di_container.register("env", boot_config)
        di_container.register("config", boot_config)
        di_container.register("event_bus", event_bus)
        di_container.register("orchestrator", orchestrator)

        modules = await boot_core_modules(
            container=di_container,
            orchestrator=orchestrator,
            config=boot_config,
            root_dir=boot_root,
        )

        try:
            assert not modules["llm"].degraded, \
                "LLM should be healthy when API key is available"
            assert modules["llm"].registered_providers, \
                "LLM should have providers when API key is set"
        finally:
            await shutdown_modules(modules)

    @pytest.mark.asyncio
    async def test_runtime_wiring_all_managers_present(
        self,
        boot_env: None,
        boot_root: Path,
        boot_config: AppConfig,
        di_container: DIContainer,
        orchestrator: Orchestrator,
        event_bus: EventBus,
    ) -> None:
        """Verify every manager is properly wired into the runtime."""
        di_container.register("env", boot_config)
        di_container.register("config", boot_config)
        di_container.register("event_bus", event_bus)
        di_container.register("orchestrator", orchestrator)

        modules = await boot_core_modules(
            container=di_container,
            orchestrator=orchestrator,
            config=boot_config,
            root_dir=boot_root,
        )

        try:
            runtime = modules["runtime"]
            for attr in ("_context_manager", "_prompt_manager",
                         "_llm_manager", "_tool_manager",
                         "_memory_manager", "_conversation_manager"):
                assert getattr(runtime, attr, None) is not None, \
                    f"Runtime missing {attr}"
        finally:
            await shutdown_modules(modules)

    @pytest.mark.asyncio
    async def test_boot_with_feature_flags_disabled(
        self,
        boot_env: None,
        boot_root: Path,
        boot_config: AppConfig,
        di_container: DIContainer,
        orchestrator: Orchestrator,
        event_bus: EventBus,
    ) -> None:
        """Managers register capabilities even with flags disabled.
        Core capabilities (memory, llm) are always present."""
        from backend.boot import register_system_capabilities

        di_container.register("env", boot_config)
        di_container.register("config", boot_config)
        di_container.register("event_bus", event_bus)
        di_container.register("orchestrator", orchestrator)

        modules = await boot_core_modules(
            container=di_container,
            orchestrator=orchestrator,
            config=boot_config,
            root_dir=boot_root,
        )

        try:
            cap_mgr = modules["capability"]
            caps = cap_mgr.list_capabilities()
            names = {c.name for c in caps}
            assert "memory" in names
            assert "llm" in names
        finally:
            await shutdown_modules(modules)

    def test_dependency_report_format(self) -> None:
        """Verify verify_boot_health produces the expected report keys."""
        from backend.boot import verify_boot_health
        from backend.modules.utils.di import DIContainer

        container = DIContainer()
        for svc in [
            "settings_manager", "memory_manager", "context_manager",
            "capability_manager", "tool_manager", "security_manager",
            "vision_manager", "voice_manager", "browser_manager",
            "pc_control_manager", "coding_agent_manager",
            "llm_manager", "prompt_manager",
            "conversation_manager", "context_intelligence_manager",
            "runtime_manager",
        ]:
            container.register(svc, object())

        modules = {name: object() for name in [
            "settings", "memory", "context", "capability", "tools",
            "security", "vision", "voice", "browser", "pc_control",
            "coding_agent", "llm", "prompt", "conversation",
            "context_intelligence", "runtime",
        ]}


        report = verify_boot_health(modules, container)
        assert "all_healthy" in report
        assert "degraded_modules" in report
        assert "missing_modules" in report
        assert "missing_services" in report
        assert "module_count" in report
        assert "service_count" in report
