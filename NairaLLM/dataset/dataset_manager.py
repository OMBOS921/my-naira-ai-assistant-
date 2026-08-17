"""
Dataset Manager for NairaLLM.

Handles canonical JSONL parsing, validation, normalization, deduplication,
splitting, challenge-set handling, failure management, and dataset reporting.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
from collections import Counter
from pathlib import Path
from typing import Any

from NairaLLM.dataset.schemas.dataset_schema import (
    DatasetFamily,
    Language,
    NairaDatasetSample,
)

_LOG = logging.getLogger("nairallm.dataset")


class DatasetManager:
    """Manager for NairaLLM training datasets."""

    def __init__(self, root_dir: str | Path | None = None) -> None:
        if root_dir is None:
            self.root_dir = Path(__file__).resolve().parent
        else:
            self.root_dir = Path(root_dir)

        self.raw_dir = self.root_dir / "raw"
        self.normalized_dir = self.root_dir / "normalized"
        self.reviewed_dir = self.root_dir / "reviewed"
        self.train_dir = self.root_dir / "train"
        self.val_dir = self.root_dir / "validation"
        self.test_dir = self.root_dir / "test"
        self.challenge_dir = self.root_dir / "challenge"
        self.failures_dir = self.root_dir / "failures"

        for directory in (
            self.raw_dir,
            self.normalized_dir,
            self.reviewed_dir,
            self.train_dir,
            self.val_dir,
            self.test_dir,
            self.challenge_dir,
            self.failures_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def load_jsonl(self, file_path: str | Path) -> list[NairaDatasetSample]:
        """Load and parse JSONL file into validated NairaDatasetSample objects."""
        path = Path(file_path)
        if not path.exists():
            return []

        samples: list[NairaDatasetSample] = []
        with open(path, "r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    sample = NairaDatasetSample.model_validate(data)
                    samples.append(sample)
                except Exception as exc:
                    _LOG.warning("Failed to parse sample at %s line %d: %s", path.name, line_idx, exc)
                    raise ValueError(f"Invalid sample in {path.name}:{line_idx} — {exc}") from exc
        return samples

    def save_jsonl(self, samples: list[NairaDatasetSample], file_path: str | Path) -> None:
        """Serialize a list of NairaDatasetSample objects into canonical JSONL."""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for sample in samples:
                line = sample.model_dump_json()
                f.write(line + "\n")

    def normalize_sample(self, sample: NairaDatasetSample) -> NairaDatasetSample:
        """Normalize whitespace and structural formatting of a sample."""
        normalized_convs = []
        for msg in sample.conversations:
            clean_content = msg.content.strip()
            normalized_convs.append(
                msg.model_copy(update={"content": clean_content})
            )
        return sample.model_copy(
            update={
                "conversations": normalized_convs,
                "system_prompt": sample.system_prompt.strip(),
            }
        )

    def deduplicate(self, samples: list[NairaDatasetSample]) -> list[NairaDatasetSample]:
        """Remove exact duplicate samples based on canonical content hash."""
        seen_hashes: set[str] = set()
        deduped: list[NairaDatasetSample] = []

        for s in samples:
            content_repr = "".join(f"{m.role}:{m.content}" for m in s.conversations)
            tool_repr = json.dumps([t.model_dump() for t in s.target_tool_calls], sort_keys=True)
            sample_hash = hashlib.sha256(f"{s.family}:{content_repr}:{tool_repr}".encode("utf-8")).hexdigest()

            if sample_hash not in seen_hashes:
                seen_hashes.add(sample_hash)
                deduped.append(s)

        return deduped

    def split_dataset(
        self,
        samples: list[NairaDatasetSample],
        train_ratio: float = 0.8,
        val_ratio: float = 0.1,
        test_ratio: float = 0.1,
        seed: int = 42,
    ) -> tuple[list[NairaDatasetSample], list[NairaDatasetSample], list[NairaDatasetSample]]:
        """Stratified / balanced split into Train, Validation, and Test sets."""
        assert abs((train_ratio + val_ratio + test_ratio) - 1.0) < 1e-5, "Ratios must sum to 1.0"
        
        # Group by family to maintain balanced coverage
        by_family: dict[DatasetFamily, list[NairaDatasetSample]] = {}
        for s in samples:
            by_family.setdefault(s.family, []).append(s)

        train_set: list[NairaDatasetSample] = []
        val_set: list[NairaDatasetSample] = []
        test_set: list[NairaDatasetSample] = []

        rng = random.Random(seed)

        for family, items in by_family.items():
            shuffled = list(items)
            rng.shuffle(shuffled)

            n_total = len(shuffled)
            n_val = max(1, int(n_total * val_ratio)) if n_total >= 4 else 0
            n_test = max(1, int(n_total * test_ratio)) if n_total >= 4 else 0
            n_train = n_total - n_val - n_test

            train_set.extend(shuffled[:n_train])
            val_set.extend(shuffled[n_train : n_train + n_val])
            test_set.extend(shuffled[n_train + n_val :])

        rng.shuffle(train_set)
        rng.shuffle(val_set)
        rng.shuffle(test_set)

        return train_set, val_set, test_set

    def compute_statistics(self, samples: list[NairaDatasetSample]) -> dict[str, Any]:
        """Compute summary statistics for dataset reporting."""
        total_samples = len(samples)
        if total_samples == 0:
            return {"total_samples": 0}

        families = Counter(s.family.value for s in samples)
        languages = Counter(s.language.value for s in samples)
        difficulties = Counter(s.difficulty for s in samples)
        total_turns = sum(len(s.conversations) for s in samples)
        total_tool_calls = sum(len(s.target_tool_calls) for s in samples)
        avg_quality = sum(s.quality_score for s in samples) / total_samples

        tool_names = Counter(
            tc.name for s in samples for tc in s.target_tool_calls
        )

        return {
            "total_samples": total_samples,
            "total_turns": total_turns,
            "avg_turns_per_sample": round(total_turns / total_samples, 2),
            "total_target_tool_calls": total_tool_calls,
            "avg_quality_score": round(avg_quality, 4),
            "families_distribution": dict(families),
            "languages_distribution": dict(languages),
            "difficulties_distribution": dict(difficulties),
            "tool_usage_frequency": dict(tool_names),
        }
