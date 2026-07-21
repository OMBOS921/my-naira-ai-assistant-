"""Tests for SkillPort, SkillMetadata, SkillResult, SkillCapability, SkillStatistics."""

from __future__ import annotations

import time

import pytest

from backend.modules.coding_agent.skills._types import (
    SkillCapability,
    SkillMetadata,
    SkillResult,
    SkillStatistics,
)


class TestSkillMetadata:
    def test_metadata_defaults(self) -> None:
        meta = SkillMetadata(
            name="Test Skill",
            description="A test skill pack",
        )
        assert meta.name == "Test Skill"
        assert meta.priority == 100
        assert meta.supported_languages == ()
        assert meta.supported_frameworks == ()
        assert meta.supported_file_extensions == ()

    def test_metadata_full(self) -> None:
        meta = SkillMetadata(
            name="Python Expert",
            description="Python domain expert",
            supported_languages=("python",),
            supported_frameworks=("django", "fastapi"),
            supported_file_extensions=(".py", ".pyi"),
            priority=90,
        )
        assert meta.name == "Python Expert"
        assert "python" in meta.supported_languages
        assert "django" in meta.supported_frameworks
        assert ".py" in meta.supported_file_extensions
        assert meta.priority == 90


class TestSkillCapability:
    def test_capability_default_confidence(self) -> None:
        cap = SkillCapability(name="test", description="Test capability")
        assert cap.confidence == 1.0

    def test_capability_custom(self) -> None:
        cap = SkillCapability(name="python", description="Python expertise", confidence=0.95)
        assert cap.name == "python"
        assert cap.confidence == 0.95


class TestSkillResult:
    def test_ok_result(self) -> None:
        result = SkillResult.ok(content="success")
        assert result.success
        assert result.content == "success"
        assert result.errors == []

    def test_fail_result(self) -> None:
        result = SkillResult.fail(error="something went wrong")
        assert not result.success
        assert result.errors == ["something went wrong"]

    def test_result_with_suggestions(self) -> None:
        result = SkillResult.ok(
            content="analysis",
            suggestions=["fix this", "improve that"],
            warnings=["caution"],
        )
        assert result.suggestions == ["fix this", "improve that"]
        assert result.warnings == ["caution"]

    def test_result_duration_default(self) -> None:
        result = SkillResult.ok()
        assert result.duration_ms == 0.0

    def test_result_metadata(self) -> None:
        result = SkillResult.ok(metadata={"key": "value"})
        assert result.metadata["key"] == "value"


class TestSkillStatistics:
    def test_initial_state(self) -> None:
        stats = SkillStatistics()
        assert stats.total_requests == 0
        assert stats.successful_executions == 0
        assert stats.failed_executions == 0
        assert stats.average_latency_ms == 0.0

    def test_record_success(self) -> None:
        stats = SkillStatistics()
        stats.record(100.0, success=True)
        assert stats.total_requests == 1
        assert stats.successful_executions == 1
        assert stats.failed_executions == 0
        assert stats.average_latency_ms == 100.0

    def test_record_failure(self) -> None:
        stats = SkillStatistics()
        stats.record(50.0, success=False)
        assert stats.total_requests == 1
        assert stats.successful_executions == 0
        assert stats.failed_executions == 1

    def test_multiple_records(self) -> None:
        stats = SkillStatistics()
        stats.record(100.0, True)
        stats.record(200.0, True)
        stats.record(50.0, False)
        assert stats.total_requests == 3
        assert stats.successful_executions == 2
        assert stats.failed_executions == 1
        assert stats.average_latency_ms == pytest.approx(116.67, rel=0.01)

    def test_last_request_time(self) -> None:
        stats = SkillStatistics()
        before = time.time()
        stats.record(10.0, True)
        assert stats.last_request_time >= before
