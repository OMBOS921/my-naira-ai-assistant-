"""
Conversation module — central runtime brain.

19_Request_Lifecycle.md — Full request lifecycle.
07_Module_Design.md §2 — Module responsibilities.

Public API
----------
- ``ConversationManager`` — central conversation manager
"""

from __future__ import annotations

from backend.modules.conversation.conversation_module import ConversationManager

__all__ = [
    "ConversationManager",
]
