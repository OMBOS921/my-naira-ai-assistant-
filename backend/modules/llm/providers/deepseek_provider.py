"""DeepSeekProvider — LLM provider for DeepSeek API using requests.

Updates the API request URL to exactly: https://opencode.ai/zen/v1/chat/completions
Updates the model name in the JSON payload to exactly: deepseek-v4-flash-free
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any

import requests

from dotenv import load_dotenv

from backend.exceptions import LLMError, ProviderAuthError, ProviderRateLimitError, ProviderTimeoutError
from backend.modules.llm.provider_base import ProviderBase
from backend.types import LLMResponse, Message, TokenUsage, ToolCall, ToolDef

load_dotenv()
_LOG = logging.getLogger("naira.llm.deepseek")


class DeepSeekProvider(ProviderBase):
    """DeepSeek LLM Provider targeting the custom completions endpoint."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "deepseek-v4-flash-free",
        timeout: int = 30,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(
            provider_name="deepseek",
            timeout=timeout,
            logger=logger or _LOG,
        )
        self._api_key = api_key
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    async def _call_provider(
        self,
        prompt: str,
        context: list[Message],
        tools: list[ToolDef] | None,
    ) -> LLMResponse:
        start_time = time.monotonic()

        messages = []
        if prompt:
            messages.append({"role": "system", "content": prompt})

        for msg in context:
            if msg.role == "system":
                messages.append({"role": "system", "content": msg.content})
            elif msg.role == "tool":
                messages.append({
                    "role": "tool",
                    "content": msg.content,
                    "tool_call_id": msg.tool_call_id or "unknown",
                })
            else:
                formatted_msg = {"role": msg.role, "content": msg.content}
                if msg.tool_calls:
                    formatted_msg["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments) if isinstance(tc.arguments, dict) else tc.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ]
                messages.append(formatted_msg)

        load_dotenv()
        api_key = os.getenv("NAIRA_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("API_KEY") or self._api_key
        if not api_key:
            return LLMResponse(
                text="SYSTEM ERROR: API Key is missing in the backend.",
                tool_calls=None,
                finish_reason="stop",
                token_usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                provider="deepseek",
                duration_ms=0.0,
            )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload: dict = {
            "model": "deepseek-v4-flash-free",
            "messages": messages,
        }

        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
                for tool in tools
            ]
            payload["tool_choice"] = "auto"

        url = "https://opencode.ai/zen/v1/chat/completions"

        def _make_request() -> requests.Response:
            return requests.post(url, json=payload, headers=headers, timeout=self._timeout)

        try:
            response = await asyncio.to_thread(_make_request)
        except requests.Timeout as exc:
            raise ProviderTimeoutError(
                f"DeepSeek request timed out after {self._timeout}s",
                context={"provider": "deepseek", "timeout": self._timeout},
            ) from exc
        except Exception as exc:
            raise LLMError(
                f"DeepSeek network/request error: {exc}",
                context={"provider": "deepseek"},
            ) from exc

        if response.status_code != 200:
            self._logger.error("DeepSeek API failed (status %d): %s", response.status_code, response.text)
            print(f"DeepSeek API Error (status {response.status_code}): {response.text}")

            if response.status_code in (401, 403):
                raise ProviderAuthError(f"DeepSeek auth failed: {response.text}", context={"status": response.status_code})
            if response.status_code == 429:
                raise ProviderRateLimitError(f"DeepSeek rate limit: {response.text}", context={"status": response.status_code})
            raise LLMError(f"DeepSeek API error: {response.text}", context={"status": response.status_code})

        try:
            data = response.json()
            text = data['choices'][0]['message']['content']
        except (ValueError, KeyError, IndexError) as exc:
            raise LLMError(f"DeepSeek response parsing failed: {exc} | Raw response: {response.text}") from exc

        choice = data["choices"][0]
        message_data = choice.get("message", {})

        tool_calls = None
        raw_tool_calls = message_data.get("tool_calls")
        if raw_tool_calls:
            tool_calls = []
            for tc in raw_tool_calls:
                func = tc.get("function", {})
                args_str = func.get("arguments") or "{}"
                try:
                    args = json.loads(args_str)
                except Exception:
                    args = {"raw_args": args_str}
                tool_calls.append(ToolCall(
                    id=tc.get("id", "unknown"),
                    name=func.get("name"),
                    arguments=args,
                ))

        raw_finish_reason = choice.get("finish_reason") or "stop"
        finish_reason = "error"
        if raw_finish_reason == "tool_calls":
            finish_reason = "tool_calls"
        elif raw_finish_reason == "length":
            finish_reason = "length"
        elif raw_finish_reason == "stop":
            finish_reason = "stop"

        usage = data.get("usage") or {}
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
        token_usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

        duration_ms = (time.monotonic() - start_time) * 1000

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            token_usage=token_usage,
            provider="deepseek",
            duration_ms=duration_ms,
        )

    async def _count_tokens_internal(self, text: str) -> int:
        return max(1, len(text) // 4)
