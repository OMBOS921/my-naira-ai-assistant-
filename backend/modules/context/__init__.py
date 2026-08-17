from __future__ import annotations
from typing import Any
"""
Any module — session-aware in-memory context management.

07_Module_Design.md §2.D.
19_Request_Lifecycle.md §3 (Phase 3: Any Assembly).

Public API
----------
- ``ContextManager`` — central context manager
"""



from backend.modules.context.context_module import ContextManager

__all__ = [
    "ContextManager",
]
