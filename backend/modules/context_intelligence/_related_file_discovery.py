"""Related File Discovery — finds files related to a given file.

Uses import relationships, shared symbols, co-occurrence patterns,
and naming conventions to discover related files.
"""

from __future__ import annotations

import logging
from pathlib import Path

from backend.modules.context_intelligence._types import FileRanking, RelatedFileSet

_LOG = logging.getLogger("naira.context_intelligence.related_file_discovery")


class RelatedFileDiscovery:
    """Discovers files related to a given source file.

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
        self._total_discoveries = 0

    def find_related(
        self,
        source_path: str,
        all_files: list[str],
        import_map: dict[str, list[str]] | None = None,
        symbol_map: dict[str, list[str]] | None = None,
        dependency_map: dict[str, list[str]] | None = None,
        top_k: int = 10,
    ) -> RelatedFileSet:
        """Find files related to a source file.

        Parameters
        ----------
        source_path : str
            Path to the source file.
        all_files : list[str]
            All candidate file paths.
        import_map : dict[str, list[str]] | None
            File to imports mapping.
        symbol_map : dict[str, list[str]] | None
            File to symbols mapping.
        dependency_map : dict[str, list[str]] | None
            File to dependencies mapping.
        top_k : int
            Maximum related files to return.

        Returns
        -------
        RelatedFileSet
            Related files with scores and relationship types.
        """
        self._total_discoveries += 1
        source_name = Path(source_path).stem
        scores: dict[str, tuple[float, list[str]]] = {}

        for file_path in all_files:
            if file_path == source_path:
                continue

            reasons: list[str] = []
            score = 0.0
            target_name = Path(file_path).stem

            # Namespace / naming relationship
            if target_name == source_name:
                score += 8.0
                reasons.append("same module name")
            elif source_name in file_path or target_name in source_path:
                score += 3.0
                reasons.append("name overlap")

            # Import relationship
            if import_map:
                source_imports = import_map.get(source_path, [])
                if source_name in source_imports:
                    score += 6.0
                    reasons.append("imported by source")
                if target_name in source_imports:
                    score += 5.0
                    reasons.append("source imports target")
                for _path, imports in import_map.items():
                    if target_name in imports and source_name in imports:
                        score += 2.0
                        reasons.append("shared import")

            # Symbol overlap
            if symbol_map:
                source_symbols = set(symbol_map.get(source_path, []))
                target_symbols = set(symbol_map.get(file_path, []))
                overlap = source_symbols & target_symbols
                if overlap:
                    score += len(overlap) * 2.0
                    reasons.append(f"shared symbols ({len(overlap)})")

            # Dependency relationship
            if dependency_map:
                source_deps = dependency_map.get(source_path, [])
                if file_path in source_deps:
                    score += 4.0
                    reasons.append("dependency")
                deps_of_target = dependency_map.get(file_path, [])
                if source_path in deps_of_target:
                    score += 4.0
                    reasons.append("depended by")

            # Directory proximity
            source_dir = Path(source_path).parent
            target_dir = Path(file_path).parent
            if source_dir == target_dir:
                score += 5.0
                reasons.append("same directory")
            elif source_dir in target_dir.parents or target_dir in source_dir.parents:
                score += 2.0
                reasons.append("nearby directory")

            if score > 0:
                scores[file_path] = (score, reasons)

        sorted_related = sorted(scores.items(), key=lambda x: x[0])
        sorted_related.sort(key=lambda x: x[1][0], reverse=True)

        rankings = [
            FileRanking(file_path=fp, score=s, reasons=rs)
            for fp, (s, rs) in sorted_related[:top_k]
        ]
        all_reasons: list[str] = []
        for _, (_, rs) in sorted_related[:top_k]:
            all_reasons.extend(rs)

        return RelatedFileSet(
            source_path=source_path,
            related_files=rankings,
            relationship_types=list(set(all_reasons)),
        )

    def find_co_occurring(
        self,
        file_paths: list[str],
        import_map: dict[str, list[str]],
    ) -> list[str]:
        """Find files that co-occur with a set of files in imports.

        Parameters
        ----------
        file_paths : list[str]
            Set of file paths to analyse.
        import_map : dict[str, list[str]]
            File to imports mapping.

        Returns
        -------
        list[str]
            Co-occurring file paths sorted by frequency.
        """
        target_imports: set[str] = set()
        for fp in file_paths:
            target_imports.update(import_map.get(fp, []))

        co_occurrence: dict[str, int] = {}
        for fp, imports in import_map.items():
            if fp in file_paths:
                continue
            overlap = target_imports & set(imports)
            if overlap:
                co_occurrence[fp] = len(overlap)

        return sorted(co_occurrence.keys(), key=lambda k: co_occurrence[k], reverse=True)

    @property
    def total_discoveries(self) -> int:
        return self._total_discoveries

    async def health_check(self) -> bool:
        return True
