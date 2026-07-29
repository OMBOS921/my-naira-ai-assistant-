"""
LLM module — manages LLM providers with Provider Orchestrator, health metrics, fallback,
generation config, and safety settings.

21_System_Contracts.md §15 — LLM Provider Contracts.
20_Dependency_Rules.md — Layer 3 (AI Core).

Public API
----------
- ``LLMManager`` — Central manager for LLM providers.
- ``LLMProviderOrchestrator`` — Orchestrator for reliable LLM execution.
- ``ModelCapabilities`` — Capabilities definition per model.
- ``ProviderHealthMetrics``, ``ProviderHealthTracker`` — Health and latency metrics.
- ``ProviderErrorCategory`` — Classified error categories.
"""

from __future__ import annotations

from backend.modules.llm.capabilities import ModelCapabilities
from backend.modules.llm.error_classifier import ProviderErrorCategory, classify_provider_error
from backend.modules.llm.generation_config import GenerationConfig
from backend.modules.llm.health import (
    ProviderHealthMetrics,
    ProviderHealthTracker,
    ProviderStatus,
)
from backend.modules.llm.llm_module import LLMManager
from backend.modules.llm.orchestrator import LLMProviderOrchestrator
from backend.modules.llm.ports.llm_port import LLMPort
from backend.modules.llm.provider_base import ProviderBase, RetryPolicy
from backend.modules.llm.safety import SafetyConfig
from backend.modules.llm.selector import ProviderSelector

__all__ = [
    "LLMManager",
    "LLMProviderOrchestrator",
    "ModelCapabilities",
    "ProviderHealthMetrics",
    "ProviderHealthTracker",
    "ProviderStatus",
    "ProviderErrorCategory",
    "classify_provider_error",
    "ProviderSelector",
    "LLMPort",
    "ProviderBase",
    "RetryPolicy",
    "GenerationConfig",
    "SafetyConfig",
]
