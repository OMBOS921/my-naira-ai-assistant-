"""
Unit tests for NairaLLM Dataset Infrastructure.
"""

from __future__ import annotations

import pytest
from NairaLLM.dataset.dataset_manager import DatasetManager
from NairaLLM.dataset.schemas.dataset_schema import (
    DatasetFamily,
    Language,
    MessageItem,
    NairaDatasetSample,
    ProvenanceMetadata,
    ToolCallItem,
)


def test_dataset_sample_validation() -> None:
    sample = NairaDatasetSample(
        id="test_001",
        family=DatasetFamily.CONVERSATION,
        language=Language.ENGLISH,
        conversations=[
            MessageItem(role="user", content="Hello"),
            MessageItem(role="assistant", content="Hi there!"),
        ],
        target_tool_calls=[],
        provenance=ProvenanceMetadata(author="test_author"),
    )
    assert sample.id == "test_001"
    assert len(sample.conversations) == 2


def test_dataset_manager_dedup_and_stats() -> None:
    dm = DatasetManager()
    sample1 = NairaDatasetSample(
        id="s1",
        family=DatasetFamily.TOOL_SELECTION,
        conversations=[MessageItem(role="user", content="Turn volume up")],
        target_tool_calls=[ToolCallItem(name="pc_system_settings", arguments={"setting": "volume", "value": 80})],
    )
    sample2 = NairaDatasetSample(
        id="s2",
        family=DatasetFamily.TOOL_SELECTION,
        conversations=[MessageItem(role="user", content="Turn volume up")],
        target_tool_calls=[ToolCallItem(name="pc_system_settings", arguments={"setting": "volume", "value": 80})],
    )

    deduped = dm.deduplicate([sample1, sample2])
    assert len(deduped) == 1

    stats = dm.compute_statistics(deduped)
    assert stats["total_samples"] == 1
    assert "pc_system_settings" in stats["tool_usage_frequency"]
