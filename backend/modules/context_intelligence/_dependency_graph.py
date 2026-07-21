"""Dependency Graph — tracks file dependency relationships.

Builds and queries a directed graph of file dependencies extracted
from import statements and other dependency relationships.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path

from backend.modules.context_intelligence._types import DependencyInfo

_LOG = logging.getLogger("naira.context_intelligence.dependency_graph")


class DependencyGraph:
    """Tracks and queries file dependency relationships.

    Parameters
    ----------
    logger : logging.Logger | None
        Module-scoped logger.
    """

    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._logger = logger or _LOG
        self._dependencies: list[DependencyInfo] = []
        self._graph: dict[str, set[str]] = {}
        self._reverse_graph: dict[str, set[str]] = {}
        self._indexed_files: set[str] = set()

    def index_file(self, file_path: str, workspace_root: str = "") -> list[DependencyInfo]:
        """Extract dependencies from a source file.

        Parameters
        ----------
        file_path : str
            Path to the source file.
        workspace_root : str
            Workspace root for resolving relative paths.

        Returns
        -------
        list[DependencyInfo]
            Extracted dependencies.
        """
        path = Path(file_path)
        if not path.is_file():
            return []

        if file_path in self._indexed_files:
            return [d for d in self._dependencies if d.source_path == file_path]

        deps: list[DependencyInfo] = []
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=file_path)
        except (SyntaxError, OSError):
            return []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    dep = DependencyInfo(
                        source_path=file_path,
                        target_path=alias.name,
                        dep_type="import",
                        line=node.lineno,
                    )
                    deps.append(dep)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    target = f"{module}.{alias.name}" if module else alias.name
                    dep = DependencyInfo(
                        source_path=file_path,
                        target_path=target,
                        dep_type="import",
                        line=node.lineno,
                    )
                    deps.append(dep)
            elif isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        dep = DependencyInfo(
                            source_path=file_path,
                            target_path=base.id,
                            dep_type="inherit",
                            line=node.lineno,
                        )
                        deps.append(dep)

        self._dependencies.extend(deps)
        self._indexed_files.add(file_path)

        for dep in deps:
            self._graph.setdefault(dep.source_path, set()).add(dep.target_path)
            self._reverse_graph.setdefault(dep.target_path, set()).add(dep.source_path)

        self._logger.debug("Extracted %d dependencies from %s", len(deps), file_path)
        return deps

    def get_dependents(self, file_path: str) -> list[str]:
        """Get files that depend on the given file.

        Parameters
        ----------
        file_path : str
            Path to the file.

        Returns
        -------
        list[str]
            Paths of dependent files.
        """
        return sorted(self._reverse_graph.get(file_path, set()))

    def get_dependencies(self, file_path: str) -> list[str]:
        """Get files that the given file depends on.

        Parameters
        ----------
        file_path : str
            Path to the file.

        Returns
        -------
        list[str]
            Paths of dependency files.
        """
        return sorted(self._graph.get(file_path, set()))

    def get_all_dependencies(self) -> list[DependencyInfo]:
        """Return all indexed dependencies.

        Returns
        -------
        list[DependencyInfo]
            All dependency records.
        """
        return list(self._dependencies)

    def find_affected_files(self, changed_file: str) -> list[str]:
        """Find all files transitively affected by a change.

        Uses BFS to traverse the reverse dependency graph.

        Parameters
        ----------
        changed_file : str
            Path to the changed file.

        Returns
        -------
        list[str]
            Transitively affected files (including the changed file).
        """
        affected: set[str] = set()
        queue = [changed_file]

        while queue:
            current = queue.pop(0)
            if current in affected:
                continue
            affected.add(current)
            dependents = self._reverse_graph.get(current, set())
            queue.extend(d for d in dependents if d not in affected)

        return sorted(affected)

    def clear(self) -> None:
        """Clear all dependency data."""
        self._dependencies.clear()
        self._graph.clear()
        self._reverse_graph.clear()
        self._indexed_files.clear()

    @property
    def dependency_count(self) -> int:
        return len(self._dependencies)

    async def health_check(self) -> bool:
        return True
