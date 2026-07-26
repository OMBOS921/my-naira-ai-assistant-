"""
Capability module — registration, lifecycle, dependency validation,
and permission integration for system capabilities.

07_Module_Design.md §1.A.

Public API
----------
- ``CapabilityManager`` — central capability manager
- ``CapabilityRegistry`` — central capability & real-time discovery registry
"""

from __future__ import annotations

from backend.modules.capability.capability import Capability
from backend.modules.capability.capability_module import CapabilityManager
from backend.modules.capability.models import (
    CapabilityCategory,
    CapabilityConfidence,
    CapabilityInfo,
    CapabilityStatus,
)
from backend.modules.capability.registry import CapabilityRegistry

__all__ = [
    "CapabilityManager",
    "CapabilityRegistry",
    "Capability",
    "CapabilityStatus",
    "CapabilityCategory",
    "CapabilityConfidence",
    "CapabilityInfo",
]
