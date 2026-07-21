from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from backend.types import Message, RequestSource


@dataclass
class RequestContext:
    request_id: uuid.UUID
    session_id: str
    source: RequestSource
    user_text: str
    messages: list[Message] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    start_time: float = 0.0
    system_prompt: str = ""
    current_stage: str = "init"
