"""Workspace Index — indexes all files in the workspace for fast retrieval.

Maintains a searchable index of workspace files with metadata including
file size, modification time, language, and line count.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from backend.modules.context_intelligence._types import IndexEntry

_LOG = logging.getLogger("naira.context_intelligence.workspace_index")

_EXCLUDED_DIRS: set[str] = {
    ".git", "__pycache__", ".venv", "venv", "node_modules",
    ".mypy_cache", ".pytest_cache", ".ruff_cache",
}

_TEXT_EXTENSIONS: set[str] = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".rs", ".go",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".swift",
    ".kt", ".md", ".json", ".yaml", ".yml", ".xml", ".html",
    ".css", ".scss", ".sql", ".toml", ".ini", ".cfg", ".txt",
    ".sh", ".bat", ".ps1", ".env", ".conf",
}


class WorkspaceIndex:
    """Indexes workspace files with metadata.

    Parameters
    ----------
    logger : logging.Logger | None
        Module-scoped logger.
    max_file_size : int
        Maximum file size in bytes to index (default 1 MB).
    """

    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
        max_file_size: int = 1_048_576,
    ) -> None:
        self._logger = logger or _LOG
        self._max_file_size = max_file_size
        self._entries: dict[str, IndexEntry] = {}
        self._last_indexed: str = ""
        self._index_count = 0

    def index_workspace(self, root_path: str) -> int:
        """Index all files in a workspace directory.

        Parameters
        ----------
        root_path : str
            Root directory to index.

        Returns
        -------
        int
            Number of files indexed.
        """
        root = Path(root_path).resolve()
        if not root.is_dir():
            self._logger.warning("Workspace path is not a directory: %s", root_path)
            return 0

        self._entries.clear()
        count = 0

        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in _EXCLUDED_DIRS]

            for filename in filenames:
                file_path = Path(dirpath) / filename
                ext = file_path.suffix.lower()

                if ext not in _TEXT_EXTENSIONS:
                    continue

                try:
                    stat = file_path.stat()
                    if stat.st_size > self._max_file_size:
                        continue
                except OSError:
                    continue

                rel_path = str(file_path.relative_to(root))
                entry = IndexEntry(
                    entry_type="file",
                    key=rel_path,
                    value={
                        "path": str(file_path),
                        "relative_path": rel_path,
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                        "language": _ext_to_language(ext),
                        "extension": ext,
                    },
                )
                self._entries[rel_path] = entry
                count += 1

        self._last_indexed = root_path
        self._index_count = count
        self._logger.debug("Indexed %d files in %s", count, root_path)
        return count

    def search(self, query: str, top_k: int = 20) -> list[IndexEntry]:
        """Search the index for files matching a query.

        Parameters
        ----------
        query : str
            Search term (matched against file paths).
        top_k : int
            Maximum results to return.

        Returns
        -------
        list[IndexEntry]
            Matching index entries.
        """
        query_lower = query.lower()
        matches: list[tuple[float, IndexEntry]] = []

        for rel_path, entry in self._entries.items():
            score = 0.0
            if query_lower in rel_path.lower():
                score = 1.0
                if rel_path.lower().endswith(query_lower):
                    score = 2.0
                if rel_path.lower().startswith(query_lower):
                    score = 1.5
            if score > 0:
                matches.append((score, entry))

        matches.sort(key=lambda x: x[0], reverse=True)
        return [m[1] for m in matches[:top_k]]

    def get_entry(self, relative_path: str) -> IndexEntry | None:
        """Get a specific index entry by relative path.

        Parameters
        ----------
        relative_path : str
            Relative path of the file.

        Returns
        -------
        IndexEntry | None
            The index entry if found.
        """
        return self._entries.get(relative_path)

    def get_all_paths(self) -> list[str]:
        """Return all indexed file paths.

        Returns
        -------
        list[str]
            Sorted list of relative paths.
        """
        return sorted(self._entries.keys())

    def language_stats(self) -> dict[str, int]:
        """Return file count by language.

        Returns
        -------
        dict[str, int]
            Language name to file count mapping.
        """
        stats: dict[str, int] = {}
        for entry in self._entries.values():
            lang = entry.value.get("language", "Unknown")
            stats[lang] = stats.get(lang, 0) + 1
        return stats

    def clear(self) -> None:
        """Clear the index."""
        self._entries.clear()
        self._index_count = 0
        self._last_indexed = ""

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    @property
    def last_indexed(self) -> str:
        return self._last_indexed

    async def health_check(self) -> bool:
        return True


def _ext_to_language(ext: str) -> str:
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
        ".sh": "Shell",
        ".bat": "Batch",
        ".ps1": "PowerShell",
        ".txt": "Text",
    }
    return mapping.get(ext, "Unknown")
