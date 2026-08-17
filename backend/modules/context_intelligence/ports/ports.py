"""Port definitions for the Any Intelligence module.

21_System_Contracts.md §4.2 — Port/Adapter pattern with abstract interfaces.
"""

from __future__ import annotations

import abc
from typing import Any, Protocol


class MemoryPort(abc.ABC):
    """Abstract port for memory storage used by Any Intelligence."""

    @abc.abstractmethod
    async def store(self, key: str, value: Any) -> None:
        ...

    @abc.abstractmethod
    async def load(self, key: str) -> Any | None:
        ...

    @abc.abstractmethod
    async def delete(self, key: str) -> None:
        ...

    @abc.abstractmethod
    async def list_keys(self, prefix: str) -> list[str]:
        ...

    @abc.abstractmethod
    async def health_check(self) -> bool:
        ...


class ContextPort(abc.ABC):
    """Abstract port for context operations."""

    @abc.abstractmethod
    def build_context(
        self,
        session_id: str,
        text: str,
        system_prompt: str,
    ) -> object:
        ...

    @abc.abstractmethod
    def get_session_messages(self, session_id: str) -> list[object] | None:
        ...

    @abc.abstractmethod
    def active_sessions(self) -> list[str]:
        ...

    @abc.abstractmethod
    async def health_check(self) -> bool:
        ...


class IndexPort(Protocol):
    """Protocol for index operations."""

    def index(self, terms: list[str], source_id: str) -> None:
        ...

    def search(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        ...

    def remove(self, source_id: str) -> None:
        ...

    def clear(self) -> None:
        ...
