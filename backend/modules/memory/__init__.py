"""
Memory module — persistent conversation storage and semantic index.

21_System_Contracts.md §16 — Memory Contracts.
04_Architecture.md §2 Layer 5 — Infrastructure Layer.

Public API
----------
- ``MemoryManager`` — central memory manager
"""

from __future__ import annotations

from backend.modules.memory.memory_module import MemoryManager

__all__ = [
    "MemoryManager",
]
