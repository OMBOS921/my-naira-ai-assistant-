"""Tests for the application configuration model (backend/modules/settings/_config.py).

21_System_Contracts.md §7 — Frozen dataclass tree with backward-compatible
properties and a factory function.
"""

from __future__ import annotations

import pytest

from backend.modules.settings._config import (
    AppConfig,
    ContextConfig,
    EventBusConfig,
    LLMConfig,
    LogConfig,
    ModulesConfig,
    SecurityConfig,
    build_app_config,
)


class TestLogConfig:
    def test_defaults(self) -> None:
        cfg = LogConfig()
        assert cfg.level == "INFO"
        assert cfg.directory == "logs"
        assert cfg.max_bytes == 10_485_760
        assert cfg.backup_count == 30

    def test_custom(self) -> None:
        cfg = LogConfig(level="DEBUG", directory="test_logs", max_bytes=512, backup_count=5)
        assert cfg.level == "DEBUG"
        assert cfg.directory == "test_logs"
        assert cfg.max_bytes == 512
        assert cfg.backup_count == 5


class TestSecurityConfig:
    def test_defaults(self) -> None:
        cfg = SecurityConfig()
        assert cfg.max_input_length == 32768
        assert cfg.allowed_paths == ()
        assert cfg.blocked_paths == ()

    def test_with_paths(self) -> None:
        cfg = SecurityConfig(
            max_input_length=1000,
            allowed_paths=("/home/user/docs",),
            blocked_paths=("/windows",),
        )
        assert cfg.max_input_length == 1000
        assert cfg.allowed_paths == ("/home/user/docs",)
        assert cfg.blocked_paths == ("/windows",)


class TestContextConfig:
    def test_defaults(self) -> None:
        cfg = ContextConfig()
        assert cfg.max_tokens == 4096

    def test_custom(self) -> None:
        cfg = ContextConfig(max_tokens=8192)
        assert cfg.max_tokens == 8192


class TestLLMConfig:
    def test_defaults(self) -> None:
        cfg = LLMConfig()
        assert cfg.active_provider == "deepseek"
        assert cfg.timeout == 30
        assert cfg.fallback_chain == ("deepseek",)

    def test_custom(self) -> None:
        cfg = LLMConfig(active_provider="ollama", timeout=60, fallback_chain=("ollama",))
        assert cfg.active_provider == "ollama"
        assert cfg.timeout == 60
        assert cfg.fallback_chain == ("ollama",)


class TestModulesConfig:
    def test_defaults(self) -> None:
        cfg = ModulesConfig()
        assert cfg.unload_after_seconds == 300
        assert cfg.lazy_load_timeout == 30

    def test_custom(self) -> None:
        cfg = ModulesConfig(unload_after_seconds=600, lazy_load_timeout=60)
        assert cfg.unload_after_seconds == 600
        assert cfg.lazy_load_timeout == 60


class TestEventBusConfig:
    def test_defaults(self) -> None:
        cfg = EventBusConfig()
        assert cfg.max_queue_size == 1000

    def test_custom(self) -> None:
        cfg = EventBusConfig(max_queue_size=500)
        assert cfg.max_queue_size == 500


class TestAppConfig:
    def test_default_construction(self) -> None:
        cfg = AppConfig()
        assert isinstance(cfg.log, LogConfig)
        assert isinstance(cfg.security, SecurityConfig)
        assert isinstance(cfg.contextConfig)
        assert isinstance(cfg.llm, LLMConfig)
        assert isinstance(cfg.modules, ModulesConfig)
        assert isinstance(cfg.event_bus, EventBusConfig)

    def test_frozen(self) -> None:
        cfg = AppConfig()
        with pytest.raises(AttributeError):
            cfg.log = LogConfig()  # type: ignore[misc]

    def test_backward_compat_log_level(self) -> None:
        cfg = AppConfig()
        assert cfg.log_level == "INFO"
        assert cfg.log_level == cfg.log.level

    def test_backward_compat_log_dir(self) -> None:
        cfg = AppConfig()
        assert cfg.log_dir == "logs"
        assert cfg.log_dir == cfg.log.directory

    def test_custom_sections(self) -> None:
        cfg = AppConfig(
            log=LogConfig(level="DEBUG", directory="custom_logs"),
            llm=LLMConfig(active_provider="ollama"),
        )
        assert cfg.log.level == "DEBUG"
        assert cfg.log.directory == "custom_logs"
        assert cfg.llm.active_provider == "ollama"
        assert cfg.security.max_input_length == 32768  # unchanged default


class TestBuildAppConfig:
    def test_empty_dict_returns_defaults(self) -> None:
        cfg = build_app_config({})
        assert cfg.log.level == "INFO"
        assert cfg.llm.active_provider == "gemini"

    def test_partial_overrides(self) -> None:
        cfg = build_app_config({"log": {"level": "DEBUG"}})
        assert cfg.log.level == "DEBUG"
        assert cfg.log.directory == "logs"  # default

    def test_nested_overrides(self) -> None:
        cfg = build_app_config({
            "log": {"level": "WARNING", "max_bytes": 999},
            "llm": {"active_provider": "deepseek"},
        })
        assert cfg.log.level == "WARNING"
        assert cfg.log.max_bytes == 999
        assert cfg.llm.active_provider == "deepseek"
        assert cfg.llm.timeout == 30  # default

    def test_unknown_keys_ignored(self) -> None:
        cfg = build_app_config({"unknown_section": {"foo": "bar"}})
        assert not hasattr(cfg, "unknown_section")

    def test_non_dict_section_falls_back(self) -> None:
        cfg = build_app_config({"log": "not_a_dict"})
        assert cfg.log.level == "INFO"  # default

    def test_type_coercion(self) -> None:
        cfg = build_app_config({
            "log": {"max_bytes": "999999"},
            "context": {"max_tokens": "2048"},
        })
        assert cfg.log.max_bytes == 999999
        assert cfg.context.max_tokens == 2048

    def test_tuple_paths(self) -> None:
        cfg = build_app_config({
            "security": {
                "allowed_paths": ["/a", "/b"],
                "blocked_paths": ["/c"],
            },
        })
        assert cfg.security.allowed_paths == ("/a", "/b")
        assert cfg.security.blocked_paths == ("/c",)
