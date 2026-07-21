"""
Prompt template data model — a frozen dataclass representing a
loaded system prompt template.

19_Request_Lifecycle.md §4 — Prompt Manager loads the system prompt
template from ``backend/modules/prompt/templates/``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptTemplate:
    """An immutable loaded prompt template.

    Parameters
    ----------
    name : str
        Template identifier (e.g. ``"system"``, ``"tool_result"``).
    content : str
        Raw template text with ``{{ variable }}`` placeholders.
    source : str
        Origin of the template (file path or ``"built-in"``).
    """

    name: str
    content: str
    source: str
