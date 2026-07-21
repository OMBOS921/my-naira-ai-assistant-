"""Repository Map — builds a structured tree of the project directory.

Walks the filesystem to produce a RepositoryNode tree representing
the project's directory structure with file sizes and language info.
"""

from __future__ import annotations

import logging
from pathlib import Path

from backend.modules.context_intelligence._types import RepositoryNode

_LOG = logging.getLogger("naira.context_intelligence.repository_map")

_EXCLUDED_DIRS: set[str] = {
    ".git", "__pycache__", ".venv", "venv", "node_modules",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".eggs",
    "dist", "build", ".tox", ".nox",
}

_EXCLUDED_EXTENSIONS: set[str] = {
    ".pyc", ".pyo", ".so", ".dll", ".dylib", ".exe",
    ".bin", ".o", ".a", ".lib", ".obj",
}


class RepositoryMap:
    """Builds and caches the repository directory tree.

    Parameters
    ----------
    logger : logging.Logger | None
        Module-scoped logger.
    max_depth : int
        Maximum directory depth to traverse (default 20).
    """

    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
        max_depth: int = 20,
    ) -> None:
        self._logger = logger or _LOG
        self._max_depth = max_depth
        self._cached_map: RepositoryNode | None = None
        self._cached_path: str = ""
        self._build_count = 0

    def build_map(self, root_path: str) -> RepositoryNode:
        """Build a repository map starting from root_path.

        Parameters
        ----------
        root_path : str
            Root directory to map.

        Returns
        -------
        RepositoryNode
            Root node of the repository tree.
        """
        root = Path(root_path).resolve()
        self._build_count += 1
        tree = self._build_node(root, depth=0)
        self._cached_map = tree
        self._cached_path = str(root)
        self._logger.debug("Repository map built for %s", root_path)
        return tree

    def _build_node(self, path: Path, depth: int) -> RepositoryNode:
        name = path.name
        str_path = str(path)

        if path.is_file():
            ext = path.suffix.lower()
            if ext in _EXCLUDED_EXTENSIONS:
                return RepositoryNode(
                    path=str_path, name=name, node_type="file", size=0
                )
            return RepositoryNode(
                path=str_path,
                name=name,
                node_type="file",
                size=path.stat().st_size,
                language=_detect_language(ext),
            )

        if depth >= self._max_depth:
            return RepositoryNode(
                path=str_path, name=name, node_type="directory", children=()
            )

        children: list[RepositoryNode] = []
        try:
            for child in sorted(path.iterdir()):
                if child.name.startswith(".") and child.name not in (".env", ".env.example"):
                    if child.is_dir() and child.name in _EXCLUDED_DIRS:
                        continue
                    if child.name.startswith(".") and child.is_file():
                        continue
                if child.name in _EXCLUDED_DIRS:
                    continue
                children.append(self._build_node(child, depth + 1))
        except PermissionError:
            pass

        return RepositoryNode(
            path=str_path,
            name=name,
            node_type="directory",
            children=tuple(children),
        )

    def get_cached_map(self) -> RepositoryNode | None:
        """Return the cached repository map if available."""
        return self._cached_map

    def flatten_map(self, node: RepositoryNode | None = None) -> list[str]:
        """Flatten the repository map into a list of file paths.

        Parameters
        ----------
        node : RepositoryNode | None
            Starting node. Defaults to cached root.

        Returns
        -------
        list[str]
            Flattened file paths.
        """
        if node is None:
            node = self._cached_map
        if node is None:
            return []

        result: list[str] = []
        self._flatten(node, result)
        return result

    def _flatten(self, node: RepositoryNode, result: list[str]) -> None:
        if node.node_type == "file":
            result.append(node.path)
        for child in node.children:
            self._flatten(child, result)

    def search_files(
        self, pattern: str, node: RepositoryNode | None = None
    ) -> list[str]:
        """Search for files matching a pattern in the repository map.

        Parameters
        ----------
        pattern : str
            Substring to match against file paths.
        node : RepositoryNode | None
            Starting node. Defaults to cached root.

        Returns
        -------
        list[str]
            Matching file paths.
        """
        pattern_lower = pattern.lower()
        all_files = self.flatten_map(node)
        return [f for f in all_files if pattern_lower in f.lower()]

    @property
    def build_count(self) -> int:
        return self._build_count

    async def health_check(self) -> bool:
        return True


def _detect_language(extension: str) -> str:
    mapping: dict[str, str] = {
        ".py": "Python",
        ".js": "JavaScript",
        ".ts": "TypeScript",
        ".tsx": "TypeScript React",
        ".jsx": "JavaScript React",
        ".java": "Java",
        ".rs": "Rust",
        ".go": "Go",
        ".c": "C",
        ".cpp": "C++",
        ".h": "C Header",
        ".hpp": "C++ Header",
        ".cs": "C#",
        ".rb": "Ruby",
        ".php": "PHP",
        ".swift": "Swift",
        ".kt": "Kotlin",
        ".scala": "Scala",
        ".sh": "Shell",
        ".bat": "Batch",
        ".ps1": "PowerShell",
        ".md": "Markdown",
        ".json": "JSON",
        ".yaml": "YAML",
        ".yml": "YAML",
        ".xml": "XML",
        ".html": "HTML",
        ".css": "CSS",
        ".scss": "SCSS",
        ".sql": "SQL",
        ".toml": "TOML",
        ".ini": "INI",
        ".cfg": "Config",
        ".txt": "Text",
    }
    return mapping.get(extension, "Unknown")
