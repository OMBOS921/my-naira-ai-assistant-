"""
Prompt validation — checks compiled prompts for correctness and safety.

19_Request_Lifecycle.md §4 — Pure string operations; timeout should
never exceed 1 s.
"""

from __future__ import annotations

import re
from typing import Final

from backend.exceptions import NairaError

_MAX_PROMPT_LENGTH: Final[int] = 32_768
_UNRESOLVED_RE: Final[re.Pattern[str]] = re.compile(r"\{\{.*?\}\}")


class PromptValidationError(NairaError):
    """A compiled prompt failed validation."""


class PromptValidator:
    """Validates compiled prompt strings before they are sent to an LLM.

    Checks:
    - No unresolved ``{{ ... }}`` placeholders remain.
    - Prompt does not exceed the maximum configured length.
    - No obvious injection patterns (basic level).
    """

    @staticmethod
    def validate(prompt: str, max_length: int = _MAX_PROMPT_LENGTH) -> None:
        """Raise ``PromptValidationError`` if *prompt* is invalid.

        Parameters
        ----------
        prompt : str
            The fully compiled prompt text.
        max_length : int
            Maximum allowed length (default 32 768).

        Raises
        ------
        PromptValidationError
            Description of the first validation failure.
        """
        _check_unresolved(prompt)
        _check_length(prompt, max_length)
        _check_injection(prompt)


def _check_unresolved(prompt: str) -> None:
    remaining = _UNRESOLVED_RE.findall(prompt)
    if remaining:
        raise PromptValidationError(
            f"Prompt contains {len(remaining)} unresolved placeholder(s): "
            f"{' '.join(remaining[:5])}",
            context={"unresolved": remaining},
        )


def _check_length(prompt: str, max_length: int) -> None:
    if len(prompt) > max_length:
        raise PromptValidationError(
            f"Prompt length {len(prompt)} exceeds maximum {max_length}",
            context={"length": len(prompt), "max_length": max_length},
        )


def _check_injection(prompt: str) -> None:
    """Basic prompt injection detection.

    Flags patterns commonly used to override system instructions.
    This is a Phase 1 baseline; enhanced detection will be added
    in later phases per 21_System_Contracts.md §18.5.
    """
    if _IGNORE_SYSTEM_RE.search(prompt):
        msg = "Prompt contains potential injection pattern"
        raise PromptValidationError(msg, context={"pattern": "ignore_system"})


_IGNORE_SYSTEM_RE: Final[re.Pattern[str]] = re.compile(
    r"(?i)(ignore\s+(all\s+)?(prior|previous|above)\s+instructions"
    r"|disregard\s+(all\s+)?(prior|previous|above)\s+instructions)"
)
