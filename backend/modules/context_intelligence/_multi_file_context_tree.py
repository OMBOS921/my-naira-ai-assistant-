"""Multi-file Any Tree — hierarchical context assembled from multiple files.

Builds a tree structure that represents the context relationship between
multiple files, enabling the LLM to understand cross-file context.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from backend.modules.context_intelligence._types import CodeChunk

_LOG = logging.getLogger("naira.context_intelligence.multi_file_context_tree")


@dataclass
class ContextTreeNode:
    """A node in the multi-file context tree."""

    file_path: str
    chunks: list[CodeChunk] = field(default_factory=list)
    children: list[ContextTreeNode] = field(default_factory=list)
    language: str = ""
    token_count: int = 0
    relevance_score: float = 1.0


class MultiFileContextTree:
    """Builds and manages a hierarchical context tree across multiple files.

    Parameters
    ----------
    logger : logging.Logger | None
        Module-scoped logger.
    max_nodes : int
        Maximum number of nodes in the tree (default 100).
    """

    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
        max_nodes: int = 100,
    ) -> None:
        self._logger = logger or _LOG
        self._max_nodes = max_nodes
        self._trees_built = 0

    def build_tree(
        self,
        files: list[dict[str, Any]],
    ) -> ContextTreeNode:
        """Build a context tree from a list of file descriptors.

        Parameters
        ----------
        files : list[dict[str, Any]]
            List of file descriptors, each with:
            - path: str
            - chunks: list[CodeChunk] (optional)
            - language: str (optional)

        Returns
        -------
        ContextTreeNode
            Root of the context tree.
        """
        self._trees_built += 1
        if not files:
            return ContextTreeNode(file_path="<root>")

        root = ContextTreeNode(file_path="<root>")
        for idx, file_info in enumerate(files):
            if idx >= self._max_nodes:
                self._logger.warning(
                    "Max nodes (%d) reached, truncating context tree",
                    self._max_nodes,
                )
                break
            path: str = file_info.get("path", f"unknown_{idx}")
            chunks: list[CodeChunk] = file_info.get("chunks", [])
            language: str = file_info.get("language", "")

            parts = path.replace("\\", "/").split("/")
            node = self._insert_path(root, parts)
            node.file_path = path
            node.chunks = chunks
            node.language = language
            node.token_count = sum(c.token_count for c in chunks)

        self._recalculate_scores(root)
        return root

    def _insert_path(self, root: ContextTreeNode, parts: list[str]) -> ContextTreeNode:
        current = root
        for part in parts:
            found = None
            for child in current.children:
                if child.file_path == part:
                    found = child
                    break
            if found is None:
                found = ContextTreeNode(file_path=part)
                current.children.append(found)
            current = found
        return current

    def _recalculate_scores(self, node: ContextTreeNode) -> None:
        total = len(node.children) if node.children else 1
        for child in node.children:
            if child.token_count > 0:
                child.relevance_score = 1.0 / max(1, total)
            self._recalculate_scores(child)

    def flatten_tree(
        self, node: ContextTreeNode | None = None, depth: int = 0
    ) -> list[dict[str, Any]]:
        """Flatten the context tree into a list of file descriptors.

        Parameters
        ----------
        node : ContextTreeNode | None
            Starting node.
        depth : int
            Current recursion depth.

        Returns
        -------
        list[dict[str, Any]]
            Flattened file descriptors with depth info.
        """
        if node is None:
            return []
        result: list[dict[str, Any]] = []
        if node.file_path != "<root>" or depth == 0:
            entry: dict[str, Any] = {
                "path": node.file_path,
                "depth": depth,
                "language": node.language,
                "token_count": node.token_count,
                "relevance_score": node.relevance_score,
                "chunk_count": len(node.chunks),
            }
            result.append(entry)
        for child in node.children:
            result.extend(self.flatten_tree(child, depth + 1))
        return result

    def prune_by_token_budget(
        self, root: ContextTreeNode, budget: int
    ) -> ContextTreeNode:
        """Prune the tree to fit within a token budget.

        Parameters
        ----------
        root : ContextTreeNode
            Tree root to prune.
        budget : int
            Maximum token count.

        Returns
        -------
        ContextTreeNode
            Pruned tree root.
        """
        total = self._count_tokens(root)
        if total <= budget:
            return root

        nodes = self.flatten_tree(root)
        nodes_sorted = sorted(nodes, key=lambda n: n["relevance_score"])
        pruned_paths: set[str] = set()
        current_budget = total

        for node_info in nodes_sorted:
            if current_budget <= budget:
                break
            path = node_info["path"]
            if path == "<root>":
                continue
            pruned_paths.add(path)
            current_budget -= node_info["token_count"]

        return self._filter_tree(root, pruned_paths)

    def _count_tokens(self, node: ContextTreeNode) -> int:
        total = node.token_count
        for child in node.children:
            total += self._count_tokens(child)
        return total

    def _filter_tree(
        self, node: ContextTreeNode, pruned_paths: set[str]
    ) -> ContextTreeNode:
        if node.file_path in pruned_paths:
            return ContextTreeNode(file_path=node.file_path)
        new_children = [
            self._filter_tree(c, pruned_paths) for c in node.children
        ]
        new_children = [c for c in new_children if c.file_path != "<pruned>"]
        return ContextTreeNode(
            file_path=node.file_path,
            chunks=node.chunks,
            children=new_children,
            language=node.language,
            token_count=node.token_count,
            relevance_score=node.relevance_score,
        )

    @property
    def trees_built(self) -> int:
        return self._trees_built

    async def health_check(self) -> bool:
        return True
