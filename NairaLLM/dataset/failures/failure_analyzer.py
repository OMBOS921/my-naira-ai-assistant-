"""
Failure Analysis and Corrective Sample Management for NairaLLM.

Classifies failure types according to systematic error taxonomy:
- wrong_intent
- wrong_tool
- wrong_arguments
- bad_plan
- hallucinated_success
- bad_memory_behavior
- bad_browser_behavior
- coding_handoff_failure
- recovery_failure
- safety_failure
- formatting_failure
"""

from __future__ import annotations

import json
import logging
from enum import StrEnum
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field

from NairaLLM.dataset.schemas.dataset_schema import NairaDatasetSample

_LOG = logging.getLogger("nairallm.failures")


class FailureType(StrEnum):
    WRONG_INTENT = "wrong_intent"
    WRONG_TOOL = "wrong_tool"
    WRONG_ARGUMENTS = "wrong_arguments"
    BAD_PLAN = "bad_plan"
    HALLUCINATED_SUCCESS = "hallucinated_success"
    BAD_MEMORY_BEHAVIOR = "bad_memory_behavior"
    BAD_BROWSER_BEHAVIOR = "bad_browser_behavior"
    CODING_HANDOFF_FAILURE = "coding_handoff_failure"
    RECOVERY_FAILURE = "recovery_failure"
    SAFETY_FAILURE = "safety_failure"
    FORMATTING_FAILURE = "formatting_failure"


class FailureRecord(BaseModel):
    """Record of a reviewed model failure."""

    id: str
    failure_type: FailureType
    input_prompt: str
    model_output: str
    expected_output: str
    diagnosis: str
    corrective_sample_id: str | None = None
    resolved: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class FailureAnalyzer:
    """Stores, classifies, and reports failure cases to guide dataset refinement."""

    def __init__(self, failures_dir: str | Path | None = None) -> None:
        if failures_dir is None:
            self.failures_dir = Path(__file__).resolve().parent
        else:
            self.failures_dir = Path(failures_dir)
        self.failures_dir.mkdir(parents=True, exist_ok=True)
        self.records_file = self.failures_dir / "failure_cases.jsonl"

    def record_failure(
        self,
        failure_type: FailureType,
        input_prompt: str,
        model_output: str,
        expected_output: str,
        diagnosis: str,
        metadata: dict[str, Any] | None = None,
    ) -> FailureRecord:
        """Log a failure case into the failure store."""
        records = self.load_failures()
        record_id = f"fail_{len(records) + 1:04d}"
        record = FailureRecord(
            id=record_id,
            failure_type=failure_type,
            input_prompt=input_prompt,
            model_output=model_output,
            expected_output=expected_output,
            diagnosis=diagnosis,
            metadata=metadata or {},
        )

        with open(self.records_file, "a", encoding="utf-8") as f:
            f.write(record.model_dump_json() + "\n")

        _LOG.info("Recorded failure %s: %s", record_id, failure_type.value)
        return record

    def load_failures(self) -> list[FailureRecord]:
        """Load all failure records."""
        if not self.records_file.exists():
            return []
        records = []
        with open(self.records_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(FailureRecord.model_validate_json(line))
        return records

    def generate_report(self) -> dict[str, Any]:
        """Generate a taxonomy summary report of known failures."""
        records = self.load_failures()
        total = len(records)
        by_type: dict[str, int] = {}
        for r in records:
            by_type[r.failure_type.value] = by_type.get(r.failure_type.value, 0) + 1

        return {
            "total_failures_recorded": total,
            "distribution_by_type": by_type,
            "unresolved_count": sum(1 for r in records if not r.resolved),
        }
