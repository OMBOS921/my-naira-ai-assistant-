"""DiffGenerator — creates unified diffs between file versions."""

from __future__ import annotations

import difflib
import logging
from typing import Any

_LOG = logging.getLogger("naira.coding_agent.diff")


class DiffGenerator:
    """Generates unified diffs between file contents.

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

    def generate_diff(
        self,
        old_content: str,
        new_content: str,
        file_path: str = "",
    ) -> str:
        """Generate a unified diff between old and new content.

        Parameters
        ----------
        old_content : str
            Original content.
        new_content : str
            New content.
        file_path : str
            File path for the diff header.

        Returns
        -------
        str
            Unified diff string.
        """
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{file_path}" if file_path else "a/file",
            tofile=f"b/{file_path}" if file_path else "b/file",
        )
        return "".join(diff)

    def generate_summary(
        self,
        old_content: str,
        new_content: str,
    ) -> dict[str, Any]:
        """Generate a summary of changes between two versions.

        Parameters
        ----------
        old_content : str
            Original content.
        new_content : str
            New content.

        Returns
        -------
        dict[str, Any]
            Summary with line counts and change type counts.
        """
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()
        differ = difflib.Differ()
        diff_lines = list(differ.compare(old_lines, new_lines))
        added = sum(1 for line in diff_lines if line.startswith("+ "))
        removed = sum(1 for line in diff_lines if line.startswith("- "))
        return {
            "old_lines": len(old_lines),
            "new_lines": len(new_lines),
            "added": added,
            "removed": removed,
            "changed": min(added, removed),
        }
