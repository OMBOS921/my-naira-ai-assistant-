"""Cross-file Navigation — maps cross-file references and enables navigation.

Tracks references between files — imports, symbol usages, and inheritance
relationships — enabling jump-to-definition and reference lookup.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import Any

_LOG = logging.getLogger("naira.context_intelligence.cross_file_navigation")


class CrossFileNavigation:
    """Provides cross-file navigation capabilities.

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
        self._references: dict[str, list[dict[str, Any]]] = {}
        self._definitions: dict[str, list[dict[str, Any]]] = {}
        self._navigations: int = 0

    def index_file(self, file_path: str, workspace_root: str = "") -> None:
        """Extract cross-file references from a source file.

        Parameters
        ----------
        file_path : str
            Path to the source file.
        workspace_root : str
            Workspace root for resolving relative imports.
        """
        path = Path(file_path)
        if not path.is_file():
            return

        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=file_path)
        except (SyntaxError, OSError):
            return

        refs: list[dict[str, Any]] = []
        defs: list[dict[str, Any]] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    refs.append({
                        "type": "import",
                        "source": file_path,
                        "target": alias.name,
                        "line": node.lineno,
                    })
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    full_target = f"{module}.{alias.name}" if module else alias.name
                    refs.append({
                        "type": "import",
                        "source": file_path,
                        "target": full_target,
                        "line": node.lineno,
                    })
            elif isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        refs.append({
                            "type": "inherit",
                            "source": file_path,
                            "target": base.id,
                            "line": node.lineno,
                        })
                defs.append({
                    "name": node.name,
                    "type": "class",
                    "file": file_path,
                    "line": node.lineno,
                })
            elif isinstance(node, ast.FunctionDef):
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Name):
                        refs.append({
                            "type": "decorator",
                            "source": file_path,
                            "target": decorator.id,
                            "line": node.lineno,
                        })
                defs.append({
                    "name": node.name,
                    "type": "function",
                    "file": file_path,
                    "line": node.lineno,
                })

            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                refs.append({
                    "type": "call",
                    "source": file_path,
                    "target": node.func.id,
                    "line": node.lineno,
                })

        self._references[file_path] = refs
        self._definitions[file_path] = defs

    def find_references(self, symbol_name: str) -> list[dict[str, Any]]:
        """Find all references to a symbol across indexed files.

        Parameters
        ----------
        symbol_name : str
            Name of the symbol to find references for.

        Returns
        -------
        list[dict[str, Any]]
            Reference locations with file, line, and type.
        """
        results: list[dict[str, Any]] = []
        for fpath, refs in self._references.items():
            for ref in refs:
                if ref["target"] == symbol_name or ref["target"].endswith(f".{symbol_name}"):
                    results.append({
                        "file": fpath,
                        "line": ref["line"],
                        "type": ref["type"],
                        "context": f"{fpath}:{ref['line']}",
                    })
        return results

    def find_definition(self, symbol_name: str) -> list[dict[str, Any]]:
        """Find the definition location of a symbol.

        Parameters
        ----------
        symbol_name : str
            Name of the symbol to find.

        Returns
        -------
        list[dict[str, Any]]
            Definition locations with file and line.
        """
        results: list[dict[str, Any]] = []
        for _fpath, defs in self._definitions.items():
            for d in defs:
                if d["name"] == symbol_name:
                    results.append({
                        "file": d["file"],
                        "line": d["line"],
                        "type": d["type"],
                        "context": f"{d['file']}:{d['line']}",
                    })
        return results

    def get_all_references(self) -> dict[str, list[dict[str, Any]]]:
        """Return all indexed references.

        Returns
        -------
        dict[str, list[dict[str, Any]]]
            File path to list of references.
        """
        return dict(self._references)

    def get_all_definitions(self) -> dict[str, list[dict[str, Any]]]:
        """Return all indexed definitions.

        Returns
        -------
        dict[str, list[dict[str, Any]]]
            File path to list of definitions.
        """
        return dict(self._definitions)

    def clear(self) -> None:
        """Clear all indexed data."""
        self._references.clear()
        self._definitions.clear()

    @property
    def navigations(self) -> int:
        return self._navigations

    async def health_check(self) -> bool:
        return True
