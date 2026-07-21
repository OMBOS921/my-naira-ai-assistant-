"""Tests for metrics and statistics."""

from __future__ import annotations

from backend.modules.coding_agent.skills._statistics import AggregatedStatistics


class TestAggregatedStatistics:
    def test_initial_state(self) -> None:
        stats = AggregatedStatistics()
        assert stats.total_requests == 0
        assert stats.successful_executions == 0
        assert stats.failed_executions == 0
        assert stats.routing_count == 0
        assert stats.composition_count == 0

    def test_record_skill_success(self) -> None:
        stats = AggregatedStatistics()
        stats.record_skill("python", 100.0, True)
        assert stats.total_requests == 1
        assert stats.successful_executions == 1
        assert stats.failed_executions == 0
        assert stats.per_skill["python"].total_requests == 1

    def test_record_skill_failure(self) -> None:
        stats = AggregatedStatistics()
        stats.record_skill("c", 50.0, False)
        assert stats.total_requests == 1
        assert stats.successful_executions == 0
        assert stats.failed_executions == 1
        assert stats.per_skill["c"].failed_executions == 1

    def test_record_routing(self) -> None:
        stats = AggregatedStatistics()
        stats.record_routing()
        assert stats.routing_count == 1

    def test_record_composition(self) -> None:
        stats = AggregatedStatistics()
        stats.record_composition()
        assert stats.composition_count == 1

    def test_average_latency(self) -> None:
        stats = AggregatedStatistics()
        stats.record_skill("python", 100.0, True)
        stats.record_skill("python", 200.0, True)
        assert stats.average_latency_ms == 150.0

    def test_to_dict(self) -> None:
        stats = AggregatedStatistics()
        stats.record_skill("python", 100.0, True)
        stats.record_routing()
        d = stats.to_dict()
        assert d["total_requests"] == 1
        assert d["routing_count"] == 1
        assert d["per_skill"]["python"]["total_requests"] == 1
        assert "uptime_seconds" in d

    def test_multiple_skills(self) -> None:
        stats = AggregatedStatistics()
        stats.record_skill("python", 100.0, True)
        stats.record_skill("react", 200.0, True)
        stats.record_skill("python", 50.0, False)
        assert stats.total_requests == 3
        assert stats.successful_executions == 2
        assert stats.failed_executions == 1
        assert stats.per_skill["python"].total_requests == 2
        assert stats.per_skill["react"].total_requests == 1

    def test_last_error(self) -> None:
        stats = AggregatedStatistics()
        stats.record_skill("python", 100.0, True)
        assert stats.per_skill["python"].last_error is None
