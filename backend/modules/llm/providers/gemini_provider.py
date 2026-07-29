"""Google Gemini adapter backed by the official ``google-genai`` SDK."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from backend.exceptions import LLMError, ProviderAuthError, ProviderRateLimitError
from backend.modules.llm.provider_base import ProviderBase
from backend.types import LLMResponse, Message, TokenUsage, ToolDef


class GeminiProvider(ProviderBase):
    """LLMPort implementation for Gemini models."""

    def __init__(self, *, api_key: str, model: str = "gemini-1.5-flash", timeout: int = 30) -> None:
        super().__init__(provider_name="gemini", timeout=timeout)
        self._api_key = api_key.strip()
        self._model = model

    @property
    def is_available(self) -> bool:
        return bool(self._api_key)

    async def verify_key(self) -> bool:
        """Make a minimal official-SDK request to validate this credential."""
        try:
            await asyncio.to_thread(self._generate_text, "Reply with OK.")
            return True
        except (ProviderAuthError, LLMError):
            return False

    async def _call_provider(self, prompt: str, context: list[Message], tools: list[ToolDef] | None) -> LLMResponse:
        del tools  # Tool mapping is intentionally deferred until it is supported by both providers.
        contents = "\n".join(f"{message.role}: {message.content}" for message in context)
        text = await asyncio.to_thread(self._generate_text, f"{prompt}\n{contents}".strip())
        return LLMResponse(
            text=text,
            tool_calls=None,
            finish_reason="stop",
            token_usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
            provider="gemini",
            duration_ms=0.0,
        )

    async def _count_tokens_internal(self, text: str) -> int:
        return max(1, len(text) // 4)

    def _generate_text(self, contents: str) -> str:
        try:
            from google import genai

            client = genai.Client(api_key=self._api_key)
            response: Any = client.models.generate_content(model=self._model, contents=contents)
            return (getattr(response, "text", None) or "").strip()
        except Exception as exc:
            self._raise_mapped_error(exc)

    def _raise_mapped_error(self, exc: Exception) -> None:
        status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
        if status in {401, 403}:
            raise ProviderAuthError("Gemini rejected the API key", context={"provider": "gemini"}) from exc
        if status == 429:
            raise ProviderRateLimitError("Gemini rate limit exceeded", context={"provider": "gemini"}) from exc
        raise LLMError("Gemini request failed", context={"provider": "gemini", "error": str(exc)}) from exc
