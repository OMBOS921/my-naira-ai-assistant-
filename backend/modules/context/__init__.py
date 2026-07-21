"""
Context module — session-aware in-memory context management.

07_Module_Design.md §2.D.
19_Request_Lifecycle.md §3 (Phase 3: Context Assembly).

Public API
----------
- ``ContextManager`` — central context manager
"""

from __future__ import annotations

from backend.modules.context.context_module import ContextManager

__all__ = [
    "ContextManager",
]
