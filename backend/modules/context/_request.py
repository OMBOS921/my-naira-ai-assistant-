"""
RequestContext — mutable metadata for a single user request.

19_Request_Lifecycle.md §1 — Request data model.
21_System_Contracts.md §19.1—§19.5 — Naming conventions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from backend.types import RequestSource
@dataclass
class RequestContext:
    """Mutable context for a single user interaction.

    Carries all metadata associated with one request through
    the processing pipeline.  Created at Phase 1 (Capture &
    Enqueue) and available to downstream phases.

    Parameters
    ----------
    request_id : uuid.UUID
        Unique identifier for this request.
    session_id : str
        Active session token.
    raw_text : str
        Original user input before any sanitisation.
    sanitized_text : str | None
        Input after security sanitisation (``None`` until Phase 2).
    source : RequestSource
        Origin channel (``"cli"``, ``"websocket"``, or ``"voice"``).
    timestamp : float
        Unix timestamp of receipt.
    metadata : dict[str, Any]
        Extensible bag for future fields.
    """

    request_id: uuid.UUID
    session_id: str
    raw_text: str
    sanitized_text: str | None = None
    source: RequestSource = "cli"
    timestamp: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
