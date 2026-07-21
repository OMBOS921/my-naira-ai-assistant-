"""Comprehensive unit tests for the LLM module and DeepSeekProvider."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests

from backend.exceptions import (
    LLMError,
    ModuleDegradedError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from backend.modules.llm.providers.deepseek_provider import DeepSeekProvider
from backend.modules.llm.generation_config import GenerationConfig
from backend.modules.llm.llm_module import LLMManager
from backend.modules.llm.ports.llm_port import LLMPort
from backend.modules.llm.provider_base import ProviderBase, RetryPolicy
from backend.modules.llm.safety import SafetyConfig
from backend.types import LLMResponse, Message, TokenUsage, ToolCall, ToolDef


class TestGenerationConfig:
    def test_defaults(self) -> None:
        gc = GenerationConfig()
        assert gc.temperature == 0.7
        assert gc.top_p == 0.95
        assert gc.top_k == 40
        assert gc.max_output_tokens == 8192
        assert gc.stop_sequences == ()

    def test_custom_values(self) -> None:
        gc = GenerationConfig(
            temperature=0.5,
            top_p=0.9,
            top_k=20,
            max_output_tokens=1024,
            stop_sequences=("STOP",),
        )
        assert gc.temperature == 0.5
        assert gc.top_p == 0.9
        assert gc.top_k == 20
        assert gc.max_output_tokens == 1024
        assert gc.stop_sequences == ("STOP",)


class TestSafetyConfig:
    def test_defaults(self) -> None:
        sc = SafetyConfig()
        assert len(sc.settings) == 4


class TestDeepSeekProvider:
    @pytest.mark.asyncio
    async def test_deepseek_provider_calls_endpoint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NAIRA_API_KEY", "test-naira-key")
        provider = DeepSeekProvider(api_key="test-naira-key")

        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Hello from OpenCode Zen!",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }

        mock_post = MagicMock(return_value=mock_response)

        with patch("requests.post", mock_post):
            res = await provider.generate(
                prompt="test system prompt",
                context=[Message(role="user", content="hello")],
            )

        assert res.text == "Hello from OpenCode Zen!"
        assert res.provider == "deepseek"
        assert res.token_usage.total_tokens == 15

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://opencode.ai/zen/v1/chat/completions"
        assert kwargs["headers"]["Authorization"] == "Bearer test-naira-key"
        assert kwargs["json"]["model"] == "deepseek-v4-flash-free"

    @pytest.mark.asyncio
    async def test_deepseek_provider_rate_limit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NAIRA_API_KEY", "test-naira-key")
        provider = DeepSeekProvider(api_key="test-naira-key")

        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 429
        mock_response.text = "Too many requests"

        mock_post = MagicMock(return_value=mock_response)

        with patch("requests.post", mock_post):
            with pytest.raises(ProviderRateLimitError):
                await provider.generate(
                    prompt="test",
                    context=[],
                )

    @pytest.mark.asyncio
    async def test_deepseek_provider_auth_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NAIRA_API_KEY", "invalid-key")
        provider = DeepSeekProvider(api_key="invalid-key")

        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        mock_post = MagicMock(return_value=mock_response)

        with patch("requests.post", mock_post):
            with pytest.raises(ProviderAuthError):
                await provider.generate(
                    prompt="test",
                    context=[],
                )


class TestLLMManager:
    @pytest.mark.asyncio
    async def test_manager_delegation(self) -> None:
        mock_provider = MagicMock(spec=ProviderBase)
        mock_provider.provider_name = "deepseek"
        mock_provider.generate = AsyncMock(
            return_value=LLMResponse(
                text="Manager success",
                tool_calls=None,
                finish_reason="stop",
                token_usage=TokenUsage(1, 1, 2),
                provider="deepseek",
                duration_ms=10.0,
            )
        )

        from backend.modules.settings._config import AppConfig
        config = AppConfig()

        mgr = LLMManager(
            config=config,
            providers={"deepseek": mock_provider},
            active_provider="deepseek",
            fallback_chain=("deepseek",),
        )
        await mgr.async_init()

        res = await mgr.generate("test prompt", [])
        assert res.text == "Manager success"
        mock_provider.generate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_manager_degraded_no_providers(self) -> None:
        from backend.modules.settings._config import AppConfig
        config = AppConfig()

        mgr = LLMManager(
            config=config,
            providers={},
            active_provider="deepseek",
            fallback_chain=("deepseek",),
        )
        await mgr.async_init()
        assert mgr.degraded is True

        with pytest.raises(ModuleDegradedError):
            await mgr.generate("test", [])
