"""
Capability — immutable capability descriptor.

07_Module_Design.md §1.A — Capability Manager responsibilities.
21_System_Contracts.md §7 — capability descriptors.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.modules.capability.metadata import CapabilityMetadata


@dataclass(frozen=True)
class Capability:
    """Immutable descriptor for a system capability.

    Carries identity, version, runtime state, metadata, dependency,
    and permission information.  No capability implementation is
    imported — this is purely a descriptor for management purposes.

    Parameters
    ----------
    name : str
        Unique capability identifier (e.g. ``"browser"``, ``"vision"``).
    version : str
        Semantic version of the capability.
    enabled : bool
        Runtime enabled/disabled state.
    metadata : CapabilityMetadata
        Descriptive metadata (supports lazy loading).
    dependencies : tuple[str, ...]
        Names of capabilities that must be enabled first.
    required_permissions : tuple[str, ...]
        Permission keys required to use this capability.
    """

    name: str
    version: str
    enabled: bool = True
    metadata: CapabilityMetadata = field(default_factory=CapabilityMetadata)
    dependencies: tuple[str, ...] = ()
    required_permissions: tuple[str, ...] = ()
