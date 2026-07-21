"""PatchGenerator — creates and validates file patches."""

from __future__ import annotations

import difflib
import logging
from typing import Any

_LOG = logging.getLogger("naira.coding_agent.patch")


class PatchGenerator:
    """Creates, validates, and manages file patches.

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

    def generate_patch(
        self,
        file_path: str,
        old_content: str,
        new_content: str,
    ) -> str:
        """Generate a unified diff patch for a single file.

        Parameters
        ----------
        file_path : str
            Path to the file being patched.
        old_content : str
            Original file content.
        new_content : str
            New file content.

        Returns
        -------
        str
            Unified diff patch string.
        """
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
        )
        return "".join(diff)

    def validate_patch(self, patch: str) -> dict[str, Any]:
        """Validate a patch string for correctness.

        Parameters
        ----------
        patch : str
            Unified diff patch to validate.

        Returns
        -------
        dict[str, Any]
            Validation result with:
            - valid: bool
            - errors: list[str]
            - hunks: int
            - files_affected: list[str]
        """
        errors: list[str] = []
        files_affected: set[str] = set()
        hunks = 0

        if not patch.strip():
            errors.append("Patch is empty")
            return {"valid": False, "errors": errors, "hunks": 0, "files_affected": []}

        for line in patch.splitlines():
            if line.startswith("--- a/") or line.startswith("+++ b/"):
                files_affected.add(line[6:])
            elif line.startswith("@@"):
                hunks += 1
            elif line.startswith("\\ "):
                continue

        if not files_affected:
            errors.append("No files referenced in patch")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "hunks": hunks,
            "files_affected": sorted(files_affected),
        }

    def apply_patch_to_content(
        self,
        content: str,
        patch: str,
    ) -> str | None:
        """Apply a patch to content in-memory.

        Parameters
        ----------
        content : str
            Original content.
        patch : str
            Unified diff patch.

        Returns
        -------
        str | None
            Patched content, or None if patch could not be applied.
        """
        try:
            result = difflib.patch(
                content.splitlines(keepends=True),
                patch.splitlines(),
            )
            return "".join(result) if result else None
        except Exception:
            return None
