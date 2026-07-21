"""ProjectAnalyzerPort — interface for project analysis.

Defines the contract for analyzing project structure, dependencies,
and code quality metrics.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ProjectAnalyzerPort(ABC):
    """Port for project analysis.

    Analyzes project structure and code characteristics.
    """

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the analyzer is available."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name."""

    @abstractmethod
    async def analyze_structure(
        self,
        path: str,
    ) -> dict[str, Any]:
        """Analyze project structure.

        Parameters
        ----------
        path : str
            Project root directory.

        Returns
        -------
        dict[str, Any]
            Structure analysis with:
            - root: str
            - languages: list[str]
            - file_count: int
            - directory_count: int
            - main_files: list[str]
            - dependencies: list[str]
        """

    @abstractmethod
    async def analyze_dependencies(
        self,
        path: str,
        language: str,
    ) -> dict[str, Any]:
        """Analyze project dependencies.

        Parameters
        ----------
        path : str
            Project root directory.
        language : str
            Programming language.

        Returns
        -------
        dict[str, Any]
            Dependency analysis with:
            - packages: list[str]
            - package_manager: str
            - dependency_count: int
            - version: str
        """

    @abstractmethod
    async def analyze_code_quality(
        self,
        path: str,
        language: str,
    ) -> dict[str, Any]:
        """Analyze code quality metrics.

        Parameters
        ----------
        path : str
            Project root directory.
        language : str
            Programming language.

        Returns
        -------
        dict[str, Any]
            Quality metrics with:
            - complexity: float
            - maintainability: float
            - test_coverage: float
            - issues: list[dict[str, Any]]
        """

    @abstractmethod
    async def analyze_goals(
        self,
        goals: list[str],
    ) -> dict[str, Any]:
        """Analyze task goals.

        Parameters
        ----------
        goals : list[str]
            List of task goals.

        Returns
        -------
        dict[str, Any]
            Goal analysis with:
            - parsed_goals: list[str]
            - required_files: list[str]
            - estimated_complexity: str
            - subtasks: list[dict[str, Any]]
        """

    @abstractmethod
    async def close(self) -> None:
        """Release analyzer resources."""
