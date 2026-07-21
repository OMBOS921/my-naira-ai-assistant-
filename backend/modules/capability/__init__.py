"""
Capability module — registration, lifecycle, dependency validation,
and permission integration for system capabilities.

07_Module_Design.md §1.A.

Public API
----------
- ``CapabilityManager`` — central capability manager
"""

from __future__ import annotations

from backend.modules.capability.capability_module import CapabilityManager

__all__ = [
    "CapabilityManager",
]
