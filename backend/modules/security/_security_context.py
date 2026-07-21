from __future__ import annotations

from typing import Any

from backend.modules.security._types import SecurityContext


def build_security_context(
    user_id: str | None = None,
    session_id: str | None = None,
    request_id: str | None = None,
    caller: str = "system",
    metadata: dict[str, Any] | None = None,
) -> SecurityContext:
    return SecurityContext(
        user_id=user_id,
        session_id=session_id,
        request_id=request_id,
        caller=caller,
        metadata=metadata or {},
    )
