"""GeminiProvider — LLM provider for Google Gemini API Studio using requests.

Model: gemini-1.5-flash for maximum speed.
Reads GEMINI_API_KEY from environment.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from typing import Any

import requests
from dotenv import load_dotenv

from backend.exceptions import LLMError, ProviderAuthError, ProviderRateLimitError, ProviderTimeoutError
from backend.modules.llm.provider_base import ProviderBase
from backend.types import LLMResponse, Message, TokenUsage, ToolCall, ToolDef

load_dotenv()
_LOG = logging.getLogger("naira.llm.gemini")


class GeminiProvider(ProviderBase):
    """Gemini LLM Provider targeting the v1beta generateContent endpoint."""

    def __init__(
        self,
        *,
        api_key: str = "",
        model: str = "gemini-3.5-flash",
        timeout: int = 30,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(
            provider_name="gemini",
            timeout=timeout,
            logger=logger or _LOG,
        )
        self._api_key = api_key
        self._model = model or "gemini-3.5-flash"
        self._fallback_models = [
            "gemini-3.5-flash",
            "gemini-2.0-flash-exp",
            "gemini-2.5-flash",
        ]

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

        load_dotenv()
        api_key = (
            os.getenv("GEMINI_API_KEY")
            or os.getenv("NAIRA_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("API_KEY")
            or self._api_key
        )
        if not api_key:
            return LLMResponse(
                text="SYSTEM ERROR: GEMINI_API_KEY is missing in the backend.",
                tool_calls=None,
                finish_reason="stop",
                token_usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                provider="gemini",
                duration_ms=0.0,
            )

        contents = []
        for msg in context:
            text_content = (msg.content or "").strip()
            if msg.role == "tool":
                # Gemini functionResponse part under role 'user'
                tool_part = {
                    "functionResponse": {
                        "name": msg.tool_call_id or "tool",
                        "response": {"output": text_content or "success"}
                    }
                }
                if contents and contents[-1]["role"] == "user":
                    contents[-1]["parts"].append(tool_part)
                else:
                    contents.append({
                        "role": "user",
                        "parts": [tool_part],
                    })
            elif msg.role == "assistant":
                parts = []
                if text_content:
                    parts.append({"text": text_content})
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        parts.append({
                            "functionCall": {
                                "name": tc.name,
                                "args": tc.arguments or {}
                            }
                        })
                if not parts:
                    continue
                if contents and contents[-1]["role"] == "model":
                    contents[-1]["parts"].extend(parts)
                else:
                    contents.append({
                        "role": "model",
                        "parts": parts,
                    })
            else:  # user or system
                if not text_content:
                    continue
                if contents and contents[-1]["role"] == "user":
                    contents[-1]["parts"].append({"text": text_content})
                else:
                    contents.append({
                        "role": "user",
                        "parts": [{"text": text_content}],
                    })

        if not contents and prompt:
            contents.append({
                "role": "user",
                "parts": [{"text": prompt}],
            })

        payload: dict[str, Any] = {
            "contents": contents,
        }

        if prompt:
            payload["system_instruction"] = {
                "parts": [{"text": prompt}]
            }

        if tools:
            func_decls = []
            for tool in tools:
                func_decls.append({
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": _convert_schema_to_gemini(tool.parameters),
                })
            payload["tools"] = [{"function_declarations": func_decls}]

        models_to_try = [self._model] + [m for m in self._fallback_models if m != self._model]
        last_error_text = ""
        response = None

        for current_model in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent?key={api_key}"
            headers = {"Content-Type": "application/json"}

            def _make_request(req_url: str) -> requests.Response:
                return requests.post(req_url, json=payload, headers=headers, timeout=self._timeout)

            try:
                resp = await asyncio.to_thread(_make_request, url)
            except requests.Timeout as exc:
                raise ProviderTimeoutError(
                    f"Gemini request timed out after {self._timeout}s",
                    context={"provider": "gemini", "timeout": self._timeout},
                ) from exc
            except Exception as exc:
                raise LLMError(
                    f"Gemini network/request error: {exc}",
                    context={"provider": "gemini"},
                ) from exc

            if resp.status_code == 200:
                response = resp
                self._model = current_model
                break
            elif resp.status_code == 404:
                self._logger.warning("Gemini model '%s' returned 404 NOT_FOUND. Trying fallback model...", current_model)
                last_error_text = resp.text
                continue
            else:
                self._logger.error("Gemini API failed (status %d): %s", resp.status_code, resp.text)
                if resp.status_code in (401, 403):
                    raise ProviderAuthError(f"Gemini auth failed: {resp.text}", context={"status": resp.status_code})
                if resp.status_code == 429:
                    raise ProviderRateLimitError(f"Gemini rate limit: {resp.text}", context={"status": resp.status_code})
                raise LLMError(f"Gemini API error: {resp.text}", context={"status": resp.status_code})

        if response is None:
            raise LLMError(f"Gemini API all models returned 404. Last error: {last_error_text}")

        try:
            data = response.json()
            candidate = data["candidates"][0]
            parts = candidate.get("content", {}).get("parts", [])
        except (ValueError, KeyError, IndexError) as exc:
            raise LLMError(f"Gemini response parsing failed: {exc} | Raw response: {response.text}") from exc

        text_parts = []
        tool_calls = []

        for part in parts:
            if "text" in part and part["text"]:
                text_parts.append(part["text"])
            if "functionCall" in part:
                fc = part["functionCall"]
                tool_calls.append(ToolCall(
                    id=f"call_{uuid.uuid4().hex[:8]}",
                    name=fc.get("name", ""),
                    arguments=fc.get("args") or {},
                ))

        text = "".join(text_parts).strip()
        finish_reason = "tool_calls" if tool_calls else "stop"

        usage = data.get("usageMetadata") or {}
        prompt_tokens = usage.get("promptTokenCount", 0)
        completion_tokens = usage.get("candidatesTokenCount", 0)
        total_tokens = usage.get("totalTokenCount", prompt_tokens + completion_tokens)

        duration_ms = (time.monotonic() - start_time) * 1000

        return LLMResponse(
            text=text,
            tool_calls=tool_calls if tool_calls else None,
            finish_reason=finish_reason,
            token_usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            ),
            provider="gemini",
            duration_ms=duration_ms,
        )

    async def _count_tokens_internal(self, text: str) -> int:
        return max(1, len(text) // 4)


def _convert_schema_to_gemini(schema: dict[str, Any]) -> dict[str, Any]:
    """Convert standard JSON Schema to Gemini parameters format with recursive ARRAY sanitization."""
    if not isinstance(schema, dict):
        return {"type": "OBJECT", "properties": {}}

    res: dict[str, Any] = {}
    stype = str(schema.get("type", "object")).upper()
    res["type"] = stype

    if "description" in schema:
        res["description"] = str(schema["description"])

    if stype == "ARRAY":
        items = schema.get("items")
        if isinstance(items, dict):
            res["items"] = _convert_schema_to_gemini(items)
        else:
            res["items"] = {"type": "STRING"}

    if "properties" in schema and isinstance(schema["properties"], dict):
        props: dict[str, Any] = {}
        for k, v in schema["properties"].items():
            if isinstance(v, dict):
                props[k] = _convert_schema_to_gemini(v)
            else:
                props[k] = {"type": "STRING"}
        res["properties"] = props

    if "required" in schema and isinstance(schema["required"], (list, tuple)):
        res["required"] = list(schema["required"])

    return res
