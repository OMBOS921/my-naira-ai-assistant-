"""LanguageDetectorPort — interface for language detection.

Defines the contract for detecting programming languages
from files, code snippets, or directory structures.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class LanguageDetectorPort(ABC):
    """Port for language detection.

    Detects programming languages from various sources.
    """

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the language detector is available."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name."""

    @abstractmethod
    async def detect_file(
        self,
        path: str,
    ) -> str:
        """Detect the language of a file.

        Parameters
        ----------
        path : str
            Path to the file.

        Returns
        -------
        str
            Language name (e.g., "python", "javascript").
        """

    @abstractmethod
    async def detect_code(
        self,
        code: str,
    ) -> str:
        """Detect the language of code content.

        Parameters
        ----------
        code : str
            Code content.

        Returns
        -------
        str
            Language name.
        """

    @abstractmethod
    async def detect_directory(
        self,
        path: str,
    ) -> dict[str, int]:
        """Detect languages in a directory.

        Parameters
        ----------
        path : str
            Path to the directory.

        Returns
        -------
        dict[str, int]
            Mapping of language names to file counts.
        """

    @abstractmethod
    async def get_extensions(
        self,
        language: str,
    ) -> list[str]:
        """Get file extensions for a language.

        Parameters
        ----------
        language : str
            Language name.

        Returns
        -------
        list[str]
            List of file extensions (e.g., [".py", ".pyw"]).
        """

    @abstractmethod
    async def close(self) -> None:
        """Release detector resources."""
