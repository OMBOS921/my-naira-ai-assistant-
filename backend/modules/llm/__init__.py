"""
LLM module — manages LLM providers with fallback, generation config,
and safety settings.

21_System_Contracts.md §15 — LLM Provider Contracts.
20_Dependency_Rules.md — Layer 3 (AI Core).

Public API
----------
- ``LLMManager`` — Central manager for LLM providers.
- ``GeminiProvider`` — Gemini provider implementation.
- ``GenerationConfig`` — Generation parameters.
- ``SafetyConfig`` — Safety settings.
"""

from __future__ import annotations

from backend.modules.llm.generation_config import GenerationConfig
from backend.modules.llm.llm_module import LLMManager
from backend.modules.llm.ports.llm_port import LLMPort
from backend.modules.llm.provider_base import ProviderBase, RetryPolicy
from backend.modules.llm.safety import SafetyConfig

from backend.modules.llm.providers.deepseek_provider import DeepSeekProvider
from backend.modules.llm.providers.gemini_provider import GeminiProvider

__all__ = [
    "LLMManager",
    "LLMPort",
    "ProviderBase",
    "RetryPolicy",
    "GenerationConfig",
    "SafetyConfig",
    "DeepSeekProvider",
    "GeminiProvider",
]
