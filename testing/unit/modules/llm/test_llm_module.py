from typing import Any
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
from backend.types import Message, ToolCall, ToolDef
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
    async def test_deepseek_provider_verify_key_success(self) -> None:
        provider = DeepSeekProvider(api_key="valid-key")
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await provider.verify_key()
            assert result is True
            mock_get.assert_called_once_with(
                "https://opencode.ai/zen/v1/models",
                headers={"Authorization": "Bearer valid-key"}
            )

    @pytest.mark.asyncio
    async def test_deepseek_provider_verify_key_failure(self) -> None:
        provider = DeepSeekProvider(api_key="invalid-key")
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await provider.verify_key()
            assert result is False

    @pytest.mark.asyncio
    async def test_deepseek_provider_calls_endpoint(self) -> None:
        provider = DeepSeekProvider(api_key="test-naira-key")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"choices": [{"message": {"role": "assistant", "content": "Hello from OpenCode Zen!"}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}'
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

        with patch.object(provider, "_get_client", return_value=None), patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            res = await provider.generate(
                prompt="test system prompt",
                context=[Message(role="user", content="hello")],
            )

        assert res.text == "Hello from OpenCode Zen!"
        assert res.provider == "deepseek"
        assert res.token_usage.total_tokens == 15
        mock_post.assert_called_once_with(
            "https://opencode.ai/zen/v1/chat/completions",
            json={
                "model": "deepseek-v4-flash-free",
                "messages": [
                    {"role": "system", "content": "test system prompt"},
                    {"role": "user", "content": "hello"},
                ],
            },
            headers={
                "Authorization": "Bearer test-naira-key",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

    @pytest.mark.asyncio
    async def test_deepseek_provider_invalid_json(self) -> None:
        provider = DeepSeekProvider(api_key="test-naira-key")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "Internal Server Error HTML or Invalid JSON text"
        mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "doc", 0)

        with patch.object(provider, "_get_client", return_value=None), patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            with pytest.raises(LLMError) as exc_info:
                await provider.generate(
                    prompt="test prompt",
                    context=[Message(role="user", content="hello")],
                )
            assert "invalid JSON" in str(exc_info.value) or "request failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_deepseek_provider_generate_stream(self) -> None:
        provider = DeepSeekProvider(api_key="test-naira-key")
        mock_response = Any(
            text="Hello world!",
            tool_calls=None,
            finish_reason="stop",
            token_usage=Any(1, 1, 2),
            provider="deepseek",
            duration_ms=0.0,
        )

        with patch.object(provider, "generate", new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = mock_response
            chunks = []
            async for token in provider.generate_stream("test prompt", [Message(role="user", content="hi")]):
                chunks.append(token)

            assert chunks == ["Hello world!"]
            mock_generate.assert_awaited_once()


class TestLLMManager:
    @pytest.mark.asyncio
    async def test_manager_delegation(self) -> None:
        mock_provider = MagicMock(spec=ProviderBase)
        mock_provider.provider_name = "deepseek"
        mock_provider.generate = AsyncMock(
            return_value=Any(
                text="Manager success",
                tool_calls=None,
                finish_reason="stop",
                token_usage=Any(1, 1, 2),
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
