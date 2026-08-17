"""
NairaLLM Adapter for Naira OS.

Conforms to the Naira OS LLM Provider / ResponsePipeline interface:
- generate(system_prompt, messages, tool_defs, session_id) -> LLMResponse
- execute_turn(...)
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.types import Message, ToolCall, ToolDef, ToolResult
from NairaLLM.integration.tool_protocol.protocol import ToolProtocol
from NairaLLM.model.runtime.naira_runtime import NairaRuntime

_LOG = logging.getLogger("nairallm.adapter")


@dataclass
class NairaLLMResponse:
    """Outbound LLM response object compatible with Naira OS runtime."""

    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class NairaLLMAdapter:
    """Integration adapter linking NairaLLM model runtime with Naira OS."""

    def __init__(
        self,
        runtime: NairaRuntime | None = None,
        tool_protocol: ToolProtocol | None = None,
        checkpoint_path: str | Path | None = None,
    ) -> None:
        if runtime is not None:
            self.runtime = runtime
        else:
            self.runtime = NairaRuntime(checkpoint_path=checkpoint_path)

        self.tool_protocol = tool_protocol or ToolProtocol()
        self._degraded = False

    def degrade(self) -> None:
        self._degraded = True
        _LOG.warning("NairaLLMAdapter marked as degraded.")

    async def generate(
        self,
        system_prompt: str,
        messages: list[Message],
        tool_defs: list[ToolDef] | None = None,
        session_id: str = "default",
        temperature: float = 0.0,
        max_new_tokens: int = 256,
    ) -> NairaLLMResponse:
        """Generate response and parse structured tool calls."""
        if self._degraded:
            return NairaLLMResponse(
                text="NairaLLM adapter is currently degraded.",
                metadata={"degraded": True},
            )

        # Build complete prompt string for the model
        prompt = f"<|system|>\n{system_prompt}\n"
        for msg in messages:
            if msg.role == "user":
                prompt += f"<|user|>\n{msg.content}\n"
            elif msg.role == "tool":
                prompt += f"<|tool_result|>\n{msg.content}\n"
            elif msg.role == "assistant":
                prompt += f"<|assistant|>\n{msg.content}<|endoftext|>\n"

        prompt += "<|assistant|>\n"

        generated_raw = self.runtime.generate(
            prompt=prompt,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            stop_tokens=["<|endoftext|>", "<|user|>"],
        )

        # Extract structured tool calls
        raw_tool_calls = self.runtime.extract_tool_calls(generated_raw)
        validated_tool_calls: list[ToolCall] = []

        for tc in raw_tool_calls:
            try:
                val_call = self.tool_protocol.validate_tool_call(tc)
                validated_tool_calls.append(val_call)
            except Exception as exc:
                _LOG.warning("Failed to validate extracted tool call %s: %s", tc, exc)

        # Clean text for user display
        final_resp = self.runtime.extract_final_response(generated_raw) if hasattr(self.runtime, "extract_final_response") else None
        plan_resp = self.runtime.extract_plan(generated_raw) if hasattr(self.runtime, "extract_plan") else None

        if final_resp:
            clean_text = final_resp
        elif plan_resp:
            clean_text = plan_resp
        else:
            clean_text = generated_raw.replace("<|endoftext|>", "").replace("<|assistant|>", "").replace("<|system|>", "").strip()
            # Clean intent, thought tags if present
            if "<|intent|>" in clean_text:
                # If tool call was also generated, clean_text can omit the raw intent tag
                clean_text = re.sub(r"<\|intent\|>\s*[a-zA-Z0-9_-]+", "", clean_text).strip()
            if "<|thought|>" in clean_text:
                parts = clean_text.split("<|thought|>")
                clean_text = parts[-1].strip()
            # Clean leading colon or whitespace
            clean_text = re.sub(r"^[:\s]+", "", clean_text)

        return NairaLLMResponse(
            text=clean_text,
            tool_calls=validated_tool_calls,
            raw_content=generated_raw,
            metadata={"session_id": session_id, "num_tool_calls": len(validated_tool_calls)},
        )
