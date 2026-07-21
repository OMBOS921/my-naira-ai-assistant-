"""File Ranking Engine — scores and ranks files by relevance to a query.

Uses a combination of heuristics — path matching, symbol relevance,
recent modification, and dependency connectivity — to rank files.
"""

from __future__ import annotations

import logging
import time

from backend.modules.context_intelligence._types import FileRanking

_LOG = logging.getLogger("naira.context_intelligence.file_ranking")


class FileRankingEngine:
    """Ranks files by relevance to a given context or query.

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
        self._total_rankings = 0

    def rank_files(
        self,
        query: str,
        file_paths: list[str],
        file_sizes: dict[str, int] | None = None,
        file_modified: dict[str, float] | None = None,
        symbol_matches: dict[str, list[str]] | None = None,
        dependency_scores: dict[str, float] | None = None,
        top_k: int = 20,
    ) -> list[FileRanking]:
        """Rank files by relevance to a query.

        Parameters
        ----------
        query : str
            Query string to match against.
        file_paths : list[str]
            List of candidate file paths.
        file_sizes : dict[str, int] | None
            File sizes in bytes.
        file_modified : dict[str, float] | None
            Modification timestamps.
        symbol_matches : dict[str, list[str]] | None
            Symbol names matching per file.
        dependency_scores : dict[str, float] | None
            Pre-computed dependency relevance scores.
        top_k : int
            Maximum results to return.

        Returns
        -------
        list[FileRanking]
            Ranked file results with scores.
        """
        self._total_rankings += 1
        query_lower = query.lower()
        query_terms = set(query_lower.split())

        scored: list[tuple[float, str, list[str]]] = []
        now = time.time()

        for file_path in file_paths:
            score = 0.0
            reasons: list[str] = []
            path_lower = file_path.lower()

            # Path match — exact file name match
            path_parts = path_lower.replace("\\", "/").split("/")
            file_name = path_parts[-1] if path_parts else ""
            stem = file_name.rsplit(".", 1)[0] if "." in file_name else file_name

            if query_lower == stem:
                score += 10.0
                reasons.append("exact file name match")
            elif query_lower in path_lower:
                score += 5.0
                reasons.append("path substring match")

            # Term overlap
            path_terms = set(p for p in path_parts if p not in ("", "__init__", "index"))
            overlap = len(query_terms & path_terms)
            if overlap > 0:
                score += overlap * 3.0
                reasons.append(f"term overlap ({overlap} terms)")

            # Symbol matches
            if symbol_matches and file_path in symbol_matches:
                symbols = symbol_matches[file_path]
                symbol_overlap = sum(1 for s in symbols if query_lower in s.lower())
                if symbol_overlap:
                    score += symbol_overlap * 4.0
                    reasons.append(f"symbol match ({symbol_overlap} symbols)")

            # Recency bonus
            if file_modified and file_path in file_modified:
                age_hours = (now - file_modified[file_path]) / 3600
                if age_hours < 1:
                    score += 3.0
                    reasons.append("recently modified")
                elif age_hours < 24:
                    score += 1.0
                    reasons.append("modified today")

            # Small file bonus
            if file_sizes and file_path in file_sizes:
                size = file_sizes[file_path]
                if 0 < size < 5000:
                    score += 1.0
                    reasons.append("small file")

            # Dependency scores
            if dependency_scores and file_path in dependency_scores:
                dep_score = dependency_scores[file_path]
                score += dep_score * 2.0
                if dep_score > 0:
                    reasons.append("dependency relevance")

            if score > 0:
                scored.append((score, file_path, reasons))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            FileRanking(file_path=fp, score=s, reasons=rs)
            for s, fp, rs in scored[:top_k]
        ]

    def rank_by_dependency_impact(
        self,
        changed_file: str,
        all_files: list[str],
        dependency_map: dict[str, list[str]],
    ) -> list[FileRanking]:
        """Rank files by their dependency impact from a change.

        Parameters
        ----------
        changed_file : str
            The file that was changed.
        all_files : list[str]
            All candidate files.
        dependency_map : dict[str, list[str]]
            File to list of dependent files mapping.

        Returns
        -------
        list[FileRanking]
            Ranked files by impact.
        """
        self._total_rankings += 1
        affected: dict[str, float] = {}

        for file_path in all_files:
            if file_path == changed_file:
                continue
            deps = dependency_map.get(file_path, [])
            if changed_file in deps:
                affected[file_path] = affected.get(file_path, 0) + 10.0

            # Transitively affected
            for dep in deps:
                if dep in dependency_map.get(changed_file, []):
                    affected[file_path] = affected.get(file_path, 0) + 5.0

        scored = sorted(affected.items(), key=lambda x: x[1], reverse=True)
        return [
            FileRanking(file_path=fp, score=s, reasons=["dependency impact"])
            for fp, s in scored
        ]

    @property
    def total_rankings(self) -> int:
        return self._total_rankings

    async def health_check(self) -> bool:
        return True
