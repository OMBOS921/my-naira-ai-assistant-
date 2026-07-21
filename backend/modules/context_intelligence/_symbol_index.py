"""Symbol Index — indexes code symbols (classes, functions, methods, variables).

Parses Python source files to extract symbol definitions and provides
search and lookup capabilities over the indexed symbols.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import Literal

from backend.modules.context_intelligence._types import SymbolInfo

_LOG = logging.getLogger("naira.context_intelligence.symbol_index")


class SymbolIndex:
    """Indexes code symbols extracted from source files.

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
        self._symbols: dict[str, list[SymbolInfo]] = {}
        self._indexed_files: set[str] = set()
        self._symbol_count = 0

    def index_file(self, file_path: str) -> int:
        """Index symbols from a single source file.

        Parameters
        ----------
        file_path : str
            Path to the source file.

        Returns
        -------
        int
            Number of symbols indexed.
        """
        path = Path(file_path)
        if not path.is_file():
            return 0

        if file_path in self._indexed_files:
            return 0

        symbols: list[SymbolInfo] = []

        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=file_path)
        except (SyntaxError, OSError) as exc:
            self._logger.debug("Failed to parse %s: %s", file_path, exc)
            return 0

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                doc = ast.get_docstring(node) or ""
                symbols.append(SymbolInfo(
                    name=node.name,
                    symbol_type="class",
                    file_path=file_path,
                    line=node.lineno,
                    column=node.col_offset,
                    docstring=doc,
                ))
            elif isinstance(node, ast.FunctionDef):
                doc = ast.get_docstring(node) or ""
                params = [a.arg for a in node.args.args if a.arg != "self"]
                sig = f"def {node.name}({', '.join(params)})"
                parent = ""
                for parent_node in ast.walk(tree):
                    if isinstance(parent_node, ast.ClassDef):
                        for child in ast.iter_child_nodes(parent_node):
                            if child is node:
                                parent = parent_node.name
                                break
                symbols.append(SymbolInfo(
                    name=node.name,
                    symbol_type="method" if parent else "function",
                    file_path=file_path,
                    line=node.lineno,
                    column=node.col_offset,
                    parent_name=parent,
                    docstring=doc,
                    signature=sig,
                ))
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and _is_public_name(target.id):
                        symbols.append(SymbolInfo(
                            name=target.id,
                            symbol_type="variable",
                            file_path=file_path,
                            line=node.lineno,
                            column=node.col_offset,
                        ))

        self._symbols[file_path] = symbols
        self._indexed_files.add(file_path)
        self._symbol_count += len(symbols)
        self._logger.debug("Indexed %d symbols from %s", len(symbols), file_path)
        return len(symbols)

    def search(
        self,
        query: str,
        symbol_type: Literal["class", "function", "method", "variable", "import", "module"]
        | None = None,
        top_k: int = 20,
    ) -> list[SymbolInfo]:
        """Search for symbols matching a query.

        Parameters
        ----------
        query : str
            Symbol name or partial name to search for.
        symbol_type : str | None
            Filter by symbol type.
        top_k : int
            Maximum results to return.

        Returns
        -------
        list[SymbolInfo]
            Matching symbols.
        """
        query_lower = query.lower()
        matches: list[tuple[float, SymbolInfo]] = []

        for _file_path, symbols in self._symbols.items():
            for sym in symbols:
                if symbol_type and sym.symbol_type != symbol_type:
                    continue

                score = 0.0
                name_lower = sym.name.lower()

                if name_lower == query_lower:
                    score = 3.0
                elif name_lower.endswith(query_lower):
                    score = 2.0
                elif query_lower in name_lower:
                    score = 1.0

                if score > 0:
                    matches.append((score, sym))

        matches.sort(key=lambda x: x[0], reverse=True)
        return [m[1] for m in matches[:top_k]]

    def get_symbols_in_file(self, file_path: str) -> list[SymbolInfo]:
        """Get all indexed symbols in a specific file.

        Parameters
        ----------
        file_path : str
            Path to the file.

        Returns
        -------
        list[SymbolInfo]
            Symbols in the file.
        """
        return self._symbols.get(file_path, [])

    def get_symbol_by_name(self, name: str) -> list[SymbolInfo]:
        """Find all symbols with a given name.

        Parameters
        ----------
        name : str
            Symbol name to find.

        Returns
        -------
        list[SymbolInfo]
            Matching symbols across all files.
        """
        return [
            sym for symbols in self._symbols.values()
            for sym in symbols if sym.name == name
        ]

    def clear(self) -> None:
        """Clear all indexed symbols."""
        self._symbols.clear()
        self._indexed_files.clear()
        self._symbol_count = 0

    @property
    def symbol_count(self) -> int:
        return self._symbol_count

    @property
    def indexed_file_count(self) -> int:
        return len(self._indexed_files)

    async def health_check(self) -> bool:
        return True


def _is_public_name(name: str) -> bool:
    return not name.startswith("_")
