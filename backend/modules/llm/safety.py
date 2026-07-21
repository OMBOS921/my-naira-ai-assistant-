"""
Safety configuration for LLM providers — harm categories and block thresholds.

21_System_Contracts.md §15 — Safety settings passed to the provider
(e.g. Gemini ``safetySettings``).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class HarmCategory(StrEnum):
    """Categories of harmful content recognised by LLM safety filters."""

    HARASSMENT = "HARM_CATEGORY_HARASSMENT"
    HATE_SPEECH = "HARM_CATEGORY_HATE_SPEECH"
    SEXUALLY_EXPLICIT = "HARM_CATEGORY_SEXUALLY_EXPLICIT"
    DANGEROUS_CONTENT = "HARM_CATEGORY_DANGEROUS_CONTENT"


class HarmBlockThreshold(StrEnum):
    """Thresholds for blocking content in each harm category."""

    BLOCK_NONE = "BLOCK_NONE"
    BLOCK_ONLY_HIGH = "BLOCK_ONLY_HIGH"
    BLOCK_MEDIUM_AND_ABOVE = "BLOCK_MEDIUM_AND_ABOVE"
    BLOCK_LOW_AND_ABOVE = "BLOCK_LOW_AND_ABOVE"


@dataclass(frozen=True)
class SafetySetting:
    """A single safety filter — category paired with a block threshold."""

    category: HarmCategory
    threshold: HarmBlockThreshold


@dataclass(frozen=True)
class SafetyConfig:
    """Complete safety configuration — an immutable tuple of ``SafetySetting``.

    The default blocks medium-and-above for all four standard categories.
    """

    settings: tuple[SafetySetting, ...] = (
        SafetySetting(HarmCategory.HARASSMENT, HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
        SafetySetting(HarmCategory.HATE_SPEECH, HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
        SafetySetting(
            HarmCategory.SEXUALLY_EXPLICIT, HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
        ),
        SafetySetting(
            HarmCategory.DANGEROUS_CONTENT, HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
        ),
    )
