"""
ResponseParser — parse Gemini API responses (both raw JSON and SDK objects)
into typed ``LLMResponse``.

21_System_Contracts.md §15.2 — LLMResponse schema.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from backend.types import FinishReason, LLMResponse, TokenUsage, ToolCall

if TYPE_CHECKING:
    from google.genai.types import (
        Candidate,
        GenerateContentResponse,
        GenerateContentResponseUsageMetadata,
    )

_FINISH_REASON_MAP: dict[str, FinishReason] = {
    "STOP": "stop",
    "MAX_TOKENS": "length",
    "SAFETY": "error",
    "RECITATION": "error",
    "OTHER": "error",
    "FINISH_REASON_UNSPECIFIED": "error",
}


def _map_finish_reason(raw: str) -> FinishReason:
    return _FINISH_REASON_MAP.get(raw, "error")


class ResponseParser:
    """Static methods for parsing Gemini API responses."""

    @staticmethod
    def parse_generate_response(
        data: dict[str, Any],
        provider: str,
        duration_ms: float,
    ) -> LLMResponse:
        """Parse a ``generateContent`` or ``streamGenerateContent`` response JSON.

        Parameters
        ----------
        data : dict[str, Any]
            The parsed JSON body from the Gemini API.
        provider : str
            Provider name (e.g. ``"gemini"``).
        duration_ms : float
            Wall-clock duration of the request.

        Returns
        -------
        LLMResponse
            Structured, immutable response.
        """
        candidates = data.get("candidates", [])
        if not candidates:
            return LLMResponse(
                text="",
                tool_calls=None,
                finish_reason="error",
                token_usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                provider=provider,
                duration_ms=duration_ms,
            )

        candidate = candidates[0]
        text, tool_calls, finish_reason = ResponseParser._parse_candidate(candidate)
        usage = ResponseParser._parse_usage(data.get("usageMetadata", {}))

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            token_usage=usage,
            provider=provider,
            duration_ms=duration_ms,
        )

    @staticmethod
    def parse_sdk_response(
        response: GenerateContentResponse,
        provider: str,
        duration_ms: float,
    ) -> LLMResponse:
        """Parse a SDK ``GenerateContentResponse`` into ``LLMResponse``.

        Parameters
        ----------
        response : GenerateContentResponse
            The SDK response object from ``client.aio.models.generate_content()``.
        provider : str
            Provider name (e.g. ``"gemini"``).
        duration_ms : float
            Wall-clock duration of the request.

        Returns
        -------
        LLMResponse
            Structured, immutable response.
        """
        candidates = response.candidates
        if not candidates:
            return LLMResponse(
                text="",
                tool_calls=None,
                finish_reason="error",
                token_usage=TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                provider=provider,
                duration_ms=duration_ms,
            )

        candidate = candidates[0]
        text, tool_calls, finish_reason = ResponseParser._parse_sdk_candidate(candidate)
        usage = ResponseParser._parse_sdk_usage(response.usage_metadata)

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            token_usage=usage,
            provider=provider,
            duration_ms=duration_ms,
        )

    @staticmethod
    def _parse_candidate(
        candidate: dict[str, Any],
    ) -> tuple[str, list[ToolCall] | None, FinishReason]:
        content = candidate.get("content", {})
        parts: list[dict[str, Any]] = content.get("parts", [])

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for part in parts:
            if "text" in part:
                text_parts.append(part["text"])
            if "functionCall" in part:
                fc = part["functionCall"]
                tool_calls.append(
                    ToolCall(
                        id=str(uuid.uuid4()),
                        name=fc.get("name", ""),
                        arguments=fc.get("args", {}),
                    )
                )

        finish_raw: str = candidate.get("finishReason", "STOP")
        finish_reason = _map_finish_reason(finish_raw)

        if tool_calls and finish_reason == "stop":
            finish_reason = "tool_calls"

        text = " ".join(text_parts)
        return text, tool_calls or None, finish_reason

    @staticmethod
    def _parse_usage(usage: dict[str, Any]) -> TokenUsage:
        return TokenUsage(
            prompt_tokens=usage.get("promptTokenCount", 0),
            completion_tokens=usage.get("candidatesTokenCount", 0),
            total_tokens=usage.get("totalTokenCount", 0),
        )

    @staticmethod
    def _parse_sdk_candidate(
        candidate: Candidate,
    ) -> tuple[str, list[ToolCall] | None, FinishReason]:
        """Parse an SDK ``Candidate`` object into text, tool_calls, finish_reason."""
        content = getattr(candidate, "content", None)
        parts: list[Any] = getattr(content, "parts", []) if content else []

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for part in parts:
            if part.text:
                text_parts.append(part.text)
            fc = getattr(part, "function_call", None)
            if fc is not None:
                tool_calls.append(
                    ToolCall(
                        id=str(uuid.uuid4()),
                        name=getattr(fc, "name", "") or "",
                        arguments=getattr(fc, "args", {}) or {},
                    )
                )

        finish_raw: str = "STOP"
        finish_reason = getattr(candidate, "finish_reason", None)
        if finish_reason is not None:
            if hasattr(finish_reason, "value"):
                finish_raw = str(finish_reason.value)
            else:
                finish_raw = str(finish_reason)
        finish_reason_mapped = _map_finish_reason(finish_raw)

        if tool_calls and finish_reason_mapped == "stop":
            finish_reason_mapped = "tool_calls"

        text = " ".join(text_parts)
        return text, tool_calls or None, finish_reason_mapped

    @staticmethod
    def _parse_sdk_usage(
        usage: GenerateContentResponseUsageMetadata | None,
    ) -> TokenUsage:
        """Parse an SDK ``UsageMetadata`` object into ``TokenUsage``."""
        if usage is None:
            return TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)
        return TokenUsage(
            prompt_tokens=getattr(usage, "prompt_token_count", 0) or 0,
            completion_tokens=getattr(usage, "candidates_token_count", 0) or 0,
            total_tokens=getattr(usage, "total_token_count", 0) or 0,
        )
