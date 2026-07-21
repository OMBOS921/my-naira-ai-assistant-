"""
CapabilityMetadata — immutable metadata with optional lazy loading.

21_System_Contracts.md §7 — metadata contracts.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CapabilityMetadata:
    """Immutable metadata for a capability descriptor.

    Supports eager construction with all fields, or lazy construction
    via ``lazy()`` where the full metadata is resolved on first call
    to ``resolve()``.

    Parameters
    ----------
    description : str
        Human-readable description of the capability.
    version : str
        Metadata schema version.
    author : str
        Origin author or plugin identifier.
    tags : tuple[str, ...]
        Classification tags for discovery and filtering.
    """

    description: str = ""
    version: str = ""
    author: str = ""
    tags: tuple[str, ...] = ()
    _loader: Callable[[], CapabilityMetadata] | None = field(
        default=None, repr=False, compare=False
    )

    @classmethod
    def lazy(cls, loader: Callable[[], CapabilityMetadata]) -> CapabilityMetadata:
        """Create a lazy-loading metadata instance.

        The *loader* callable is invoked exactly once on the first
        call to ``resolve()``.

        Parameters
        ----------
        loader : Callable[[], CapabilityMetadata]
            Thunk that returns the fully populated metadata.
        """
        return cls(description="(lazy)", _loader=loader)

    def resolve(self) -> CapabilityMetadata:
        """Resolve lazy-loaded metadata in place.

        Returns self with fields populated from the loader if this
        instance was created via ``lazy()``.  Already-resolved
        instances return self immediately.
        """
        loader = self._loader
        if loader is not None:
            resolved = loader()
            object.__setattr__(self, "description", resolved.description)
            object.__setattr__(self, "version", resolved.version)
            object.__setattr__(self, "author", resolved.author)
            object.__setattr__(self, "tags", resolved.tags)
            object.__setattr__(self, "_loader", None)
        return self
