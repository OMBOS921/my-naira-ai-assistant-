"""OpenCode Zen adapter for the OpenAI-compatible DeepSeek endpoint."""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from collections.abc import AsyncIterator
from typing import Any

import httpx

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None

import re
import uuid

from backend.exceptions import LLMError, ProviderAuthError, ProviderRateLimitError
from backend.modules.llm.provider_base import ProviderBase
from backend.types import FinishReason, LLMResponse, Message, TokenUsage, ToolCall, ToolDef


def extract_tool_calls_from_text(
    content: str,
    tools: list[ToolDef] | None,
) -> tuple[list[ToolCall] | None, FinishReason]:
    """Extract tool calls from text content if standard tools are provided.

    Supports:
    1. Structured JSON blocks matching tool names or action parameters.
    2. Python code blocks (```python ... ```) when execute_local_python is an available tool.
    """
    if not content or not tools:
        return None, "stop"

    available_tool_names = {t.name for t in tools}
    tool_calls: list[ToolCall] = []

    # 1. Try to extract JSON tool call objects
    json_blocks = re.findall(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", content, re.IGNORECASE)
    for block in json_blocks:
        try:
            data = json.loads(block)
            if isinstance(data, dict):
                tool_name = data.get("tool") or data.get("name") or data.get("action") or ""
                args = data.get("arguments") or data.get("args") or data.get("action_input") or {}
                if tool_name in available_tool_names:
                    tool_calls.append(
                        ToolCall(
                            id=f"call_{uuid.uuid4().hex[:8]}",
                            name=str(tool_name),
                            arguments=args if isinstance(args, dict) else {"input": str(args)},
                        )
                    )
        except Exception:
            pass

    if tool_calls:
        return tool_calls, "tool_calls"

    # 2. Extract python code blocks if execute_local_python is available
    if "execute_local_python" in available_tool_names or any(t.name in ("execute_local_python", "execute_script") for t in tools):
        py_match = re.search(r"```(?:python|py)\s*\n([\s\S]+?)\s*```", content, re.IGNORECASE)
        if py_match:
            code_str = py_match.group(1).strip()
            if code_str:
                tool_name = "execute_local_python" if "execute_local_python" in available_tool_names else "execute_script"
                tool_calls.append(
                    ToolCall(
                        id=f"call_{uuid.uuid4().hex[:8]}",
                        name=tool_name,
                        arguments={"script_code": code_str},
                    )
                )
                return tool_calls, "tool_calls"

    return None, "stop"


class DeepSeekProvider(ProviderBase):
    """LLMPort implementation for OpenCode Zen's DeepSeek V4 Flash model."""

    base_url = "https://opencode.ai/zen/v1"

    def __init__(self, *, api_key: str, model: str = "deepseek-v4-flash-free", timeout: int = 60) -> None:
        super().__init__(provider_name="deepseek", timeout=timeout)
        self._api_key = api_key.strip()
        self._model = model

    @property
    def api_key(self) -> str:
        return self._api_key

    @property
    def is_available(self) -> bool:
        return bool(self._api_key)

    def _get_client(self, timeout: float = 15.0) -> Any:
        """Instantiate an AsyncOpenAI client targeting OpenCodeZen base URL if openai is installed."""
        if AsyncOpenAI is not None:
            return AsyncOpenAI(api_key=self.api_key, base_url="https://opencode.ai/zen/v1", timeout=timeout)
        return None

    async def verify_key(self) -> bool:
        """Validate the key against OpenCode Zen's dedicated models endpoint."""
        urls = [f"{self.base_url}/models", "https://opencode.ai/zen/v1/models"]
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            async with httpx.AsyncClient(timeout=min(float(self._timeout), 15.0)) as client:
                for url in urls:
                    try:
                        response = await client.get(url, headers=headers)
                        if response.status_code == 200:
                            return True
                    except Exception:
                        continue
                return False
        except Exception:
            return False

    async def generate_stream(
        self,
        prompt: str,
        context: list[Message],
        tools: list[ToolDef] | None = None,
    ) -> AsyncIterator[str]:
        """Wrap non-streaming generate() to guarantee stability and prevent SSE hangs."""
        self._logger.info("Sending streaming request to OpenCode Zen (via non-streaming fallback for stability)...")
        response = await self.generate(prompt, context, tools)
        yield response.text

    async def _call_provider(self, prompt: str, context: list[Message], tools: list[ToolDef] | None) -> LLMResponse:
        system_prompt = prompt or ""
        if tools:
            tool_names = ", ".join(t.name for t in tools)
            system_prompt += (
                f"\n\n[MANDATORY TOOL EXECUTION INSTRUCTIONS]:\n"
                f"You are an autonomous AI agent with tool execution capabilities. Available tools: [{tool_names}].\n"
                f"DO NOT output Python code in standard Markdown blocks if you intend to run it. You MUST use the `execute_local_python` tool.\n"
                f"If you intend to run code, format your output as a JSON tool call block:\n"
                f"```json\n"
                f"{{\n"
                f'  "tool": "execute_local_python",\n'
                f'  "arguments": {{\n'
                f'    "script_code": "<your complete python code>"\n'
                f"  }}\n"
                f"}}\n"
                f"```\n"
                f"You are an autonomous AI agent; do not ask for user permission, just call the tool."
            )

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend({"role": item.role if item.role != "tool" else "user", "content": item.content} for item in context)

        request_timeout = 15.0

        # Attempt to use AsyncOpenAI client with OpenCodeZen base_url if available
        client = self._get_client(timeout=request_timeout)
        if client is not None:
            try:
                self._logger.info("Sending request to OpenCode Zen...")
                response = await client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    timeout=request_timeout,
                )
                choice = response.choices[0]
                content = choice.message.content or ""
                usage = response.usage

                tool_calls, finish_reason = extract_tool_calls_from_text(content, tools)

                return LLMResponse(
                    text=content,
                    tool_calls=tool_calls,
                    finish_reason=finish_reason,
                    token_usage=TokenUsage(
                        usage.prompt_tokens if usage else 0,
                        usage.completion_tokens if usage else 0,
                        usage.total_tokens if usage else 0,
                    ),
                    provider="deepseek",
                    duration_ms=0.0,
                )
            except Exception as exc:
                status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
                if status in {401, 403}:
                    raise ProviderAuthError("OpenCode Zen rejected the API key", context={"provider": "deepseek"}) from exc
                if status == 429:
                    raise ProviderRateLimitError("OpenCode Zen rate limit exceeded", context={"provider": "deepseek"}) from exc
                raise LLMError("OpenCode Zen request failed", context={"provider": "deepseek", "error": str(exc)}) from exc

        # Fallback to direct httpx request using base_url = "https://opencode.ai/zen/v1"
        base_urls = [self.base_url, "https://opencode.ai/zen/v1"]
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {"model": self._model, "messages": messages}

        result = None
        last_exc = None

        self._logger.info("Sending request to OpenCode Zen...")
        async with httpx.AsyncClient(timeout=request_timeout) as client:
            for base in base_urls:
                url = f"{base}/chat/completions"
                try:
                    response = await client.post(url, json=payload, headers=headers)
                    if response.status_code in {401, 403}:
                        raise ProviderAuthError("OpenCode Zen rejected the API key", context={"provider": "deepseek"})
                    if response.status_code == 429:
                        raise ProviderRateLimitError("OpenCode Zen rate limit exceeded", context={"provider": "deepseek"})
                    if response.status_code == 200:
                        raw_text = response.text
                        if not raw_text or not raw_text.strip():
                            self._logger.error(f"OpenCode Zen Raw Response: {raw_text}")
                            raise LLMError(
                                "OpenCode Zen returned an empty response body",
                                context={"provider": "deepseek", "raw_response": raw_text},
                            )
                        try:
                            data = response.json()
                        except json.JSONDecodeError as json_err:
                            self._logger.error(f"OpenCode Zen Raw Response: {raw_text}")
                            raise LLMError(
                                f"OpenCode Zen returned invalid JSON: {json_err}",
                                context={"provider": "deepseek", "raw_response": raw_text},
                            ) from json_err

                        if isinstance(data, dict) and "choices" in data:
                            result = data
                            break
                except (ProviderAuthError, ProviderRateLimitError, LLMError):
                    raise
                except Exception as exc:
                    last_exc = exc
                    continue

        if result is None:
            if last_exc:
                raise LLMError("OpenCode Zen request failed", context={"provider": "deepseek", "error": str(last_exc)}) from last_exc
            raise LLMError("OpenCode Zen request failed", context={"provider": "deepseek"})

        choice = result.get("choices", [{}])[0]
        content = choice.get("message", {}).get("content", "")
        usage = result.get("usage", {})
        tool_calls, finish_reason = extract_tool_calls_from_text(content or "", tools)

        return LLMResponse(
            text=content or "",
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            token_usage=TokenUsage(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0), usage.get("total_tokens", 0)),
            provider="deepseek",
            duration_ms=0.0,
        )

    async def _count_tokens_internal(self, text: str) -> int:
        return max(1, len(text) // 4)

    def _request(self, method: str, path: str, payload: dict[str, Any] | None) -> dict[str, Any]:
        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            f"{self.base_url}{path}", data=data, method=method,
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise ProviderAuthError("OpenCode Zen rejected the API key", context={"provider": "deepseek"}) from exc
            if exc.code == 429:
                raise ProviderRateLimitError("OpenCode Zen rate limit exceeded", context={"provider": "deepseek"}) from exc
            raise LLMError("OpenCode Zen request failed", context={"provider": "deepseek", "status": exc.code}) from exc
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            raise LLMError("OpenCode Zen is unavailable", context={"provider": "deepseek", "error": str(exc)}) from exc





