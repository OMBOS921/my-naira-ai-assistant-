"""
Prompt module — system prompt template loading, compilation, and validation.

07_Module_Design.md §2.C.
19_Request_Lifecycle.md §4 (Phase 4: Prompt Compilation).

Public API
----------
- ``PromptManager`` — central prompt compilation manager
"""

from __future__ import annotations

from backend.modules.prompt.prompt_module import PromptManager

__all__ = [
    "PromptManager",
]
