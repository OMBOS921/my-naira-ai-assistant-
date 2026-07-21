"""Import Graph — tracks and analyses Python import relationships.

Builds a directed graph of import relationships between files in the
workspace, supporting cycle detection, import chain analysis, and
dependency impact analysis.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path

_LOG = logging.getLogger("naira.context_intelligence.import_graph")


class ImportGraph:
    """Tracks Python import relationships across the workspace.

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
        self._imports: dict[str, set[str]] = {}
        self._imported_by: dict[str, set[str]] = {}
        self._all_paths: set[str] = set()

    def index_file(self, file_path: str, workspace_root: str = "") -> None:
        """Extract import statements from a Python file.

        Parameters
        ----------
        file_path : str
            Path to the source file.
        workspace_root : str
            Workspace root for resolving imports.
        """
        path = Path(file_path)
        if not path.is_file():
            return

        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=file_path)
        except (SyntaxError, OSError):
            return

        self._all_paths.add(file_path)
        imports: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                top_module = module.split(".")[0] if module else ""
                if top_module:
                    imports.add(top_module)

        self._imports[file_path] = imports
        for imp in imports:
            self._imported_by.setdefault(imp, set()).add(file_path)

    def get_imports(self, file_path: str) -> list[str]:
        """Get all imports of a specific file.

        Parameters
        ----------
        file_path : str
            Path to the file.

        Returns
        -------
        list[str]
            Imported module names.
        """
        return sorted(self._imports.get(file_path, set()))

    def get_importers(self, module_name: str) -> list[str]:
        """Get all files that import a given module.

        Parameters
        ----------
        module_name : str
            Name of the module.

        Returns
        -------
        list[str]
            File paths that import the module.
        """
        return sorted(self._imported_by.get(module_name, set()))

    def detect_cycles(self) -> list[list[str]]:
        """Detect circular dependencies in the import graph.

        Uses DFS-based cycle detection.

        Returns
        -------
        list[list[str]]
            List of cycles (each cycle is a list of file paths).
        """
        cycles: list[list[str]] = []
        visited: set[str] = set()
        path: list[str] = []
        path_set: set[str] = set()

        def dfs(node: str) -> None:
            if node in path_set:
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                cycles.append(list(cycle))
                return
            if node in visited:
                return

            visited.add(node)
            path.append(node)
            path_set.add(node)

            for imp in self._imports.get(node, set()):
                if imp in self._all_paths:
                    dfs(imp)
                for importer in self._imported_by.get(imp, set()):
                    if importer in self._all_paths and importer not in visited:
                        dfs(importer)

            path.pop()
            path_set.discard(node)

        for file_path in sorted(self._all_paths):
            if file_path not in visited:
                dfs(file_path)

        return cycles

    def get_import_chain(self, source: str, target: str) -> list[str]:
        """Find the import chain between two files.

        Uses BFS to find the shortest path.

        Parameters
        ----------
        source : str
            Source file path.
        target : str
            Target file path.

        Returns
        -------
        list[str]
            Shortest import chain from source to target.
        """
        if source not in self._all_paths or target not in self._all_paths:
            return []

        visited: set[str] = {source}
        queue: list[list[str]] = [[source]]

        while queue:
            path = queue.pop(0)
            current = path[-1]

            if current == target:
                return path

            for imp in self._imports.get(current, set()):
                for candidate in self._all_paths:
                    if candidate not in visited and imp in self._imports.get(candidate, set()):
                        visited.add(candidate)
                        queue.append(path + [candidate])

            for dep in self._imported_by.get(current, set()):
                if dep not in visited:
                    visited.add(dep)
                    queue.append(path + [dep])

        return []

    def clear(self) -> None:
        """Clear all import data."""
        self._imports.clear()
        self._imported_by.clear()
        self._all_paths.clear()

    @property
    def indexed_file_count(self) -> int:
        return len(self._all_paths)

    @property
    def import_count(self) -> int:
        return sum(len(imps) for imps in self._imports.values())

    async def health_check(self) -> bool:
        return True
