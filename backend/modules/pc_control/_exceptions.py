"""PC Control exception hierarchy.

21_System_Contracts.md §3 — All application exceptions inherit from
``NairaError`` and carry a ``context`` dict.
"""

from __future__ import annotations

from typing import Any

from backend.exceptions import NairaError


class PCControlError(NairaError):
    """Base for all PC-control module errors."""


class PCControlTimeoutError(PCControlError):
    """A PC-control operation exceeded its timeout."""


class PCControlExecutionError(PCControlError):
    """A PC-control operation failed during execution."""


class PCControlPermissionError(PCControlError):
    """The requested operation was denied by the sandbox or policy."""


class PCControlNotImplementedError(PCControlError):
    """The operation is not supported by the current adapter.

    Raised by placeholder adapters (e.g. ``LocalPCControlAdapter``)
    to signal that the real implementation has not been wired yet.
    """

    def __init__(self, context: dict[str, Any] | None = None) -> None:
        super().__init__(
            "PC control adapter not available — no OS automation driver configured",
            context=context,
        )
