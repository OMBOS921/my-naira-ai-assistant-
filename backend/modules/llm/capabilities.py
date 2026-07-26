"""
ModelCapabilities — model capability definition for dynamic provider selection.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModelCapabilities:
    """Model capabilities advertised by LLM providers.

    Parameters
    ----------
    supports_tools : bool
        Whether the model supports function/tool calling (default ``True``).
    supports_streaming : bool
        Whether the model supports token streaming (default ``True``).
    supports_vision : bool
        Whether the model supports multimodal/vision inputs (default ``False``).
    supports_reasoning : bool
        Whether the model supports deep reasoning / thinking (default ``False``).
    max_context_tokens : int
        Maximum context window token limit (default ``128000``).
    max_output_tokens : int
        Maximum output token limit (default ``8192``).
    supported_mime_types : tuple[str, ...]
        MIME types supported for input files (default ``("text/plain", "application/json")``).
    custom_metadata : dict[str, str]
        Optional key-value metadata for provider-specific attributes.
    """

    supports_tools: bool = True
    supports_streaming: bool = True
    supports_vision: bool = False
    supports_reasoning: bool = False
    max_context_tokens: int = 128000
    max_output_tokens: int = 8192
    supported_mime_types: tuple[str, ...] = ("text/plain", "application/json")
    custom_metadata: dict[str, str] = field(default_factory=dict)

    def matches_requirements(
        self,
        requires_tools: bool = False,
        requires_streaming: bool = False,
        requires_vision: bool = False,
        requires_reasoning: bool = False,
        min_context_tokens: int = 0,
    ) -> bool:
        """Check whether provider model capabilities satisfy request requirements."""
        if requires_tools and not self.supports_tools:
            return False
        if requires_streaming and not self.supports_streaming:
            return False
        if requires_vision and not self.supports_vision:
            return False
        if requires_reasoning and not self.supports_reasoning:
            return False
        if min_context_tokens > 0 and self.max_context_tokens < min_context_tokens:
            return False
        return True
