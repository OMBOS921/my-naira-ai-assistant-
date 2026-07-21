"""Tests for SkillHealthReport and health subsystem."""

from __future__ import annotations

from backend.modules.coding_agent.skills._health import SkillHealthReportBuilder
from backend.modules.coding_agent.skills._statistics import AggregatedStatistics
from backend.modules.coding_agent.skills._types import SkillHealthReport


class TestSkillHealthReport:
    def test_healthy_report(self) -> None:
        report = SkillHealthReport.healthy("python", version="3.12")
        assert report.name == "python"
        assert report.is_healthy
        assert report.registered
        assert report.active
        assert report.details["version"] == "3.12"

    def test_unhealthy_report(self) -> None:
        report = SkillHealthReport.unhealthy("c", reason="not available")
        assert not report.is_healthy
        assert not report.active
        assert report.details["reason"] == "not available"

    def test_healthy_default_details(self) -> None:
        report = SkillHealthReport.healthy("test")
        assert report.details == {}


class TestSkillHealthReportBuilder:
    def test_subsystem_report_healthy(self) -> None:
        stats = AggregatedStatistics()
        report = SkillHealthReportBuilder.subsystem_report(
            registered_skills=["python", "c"],
            active_skills=["python", "c"],
            degraded=False,
            stats=stats,
        )
        assert report["subsystem"] == "skills"
        assert report["healthy"]
        assert not report["degraded"]
        assert report["registered_skills_count"] == 2
        assert report["active_skills_count"] == 2

    def test_subsystem_report_degraded(self) -> None:
        stats = AggregatedStatistics()
        report = SkillHealthReportBuilder.subsystem_report(
            registered_skills=[],
            active_skills=[],
            degraded=True,
            stats=stats,
        )
        assert not report["healthy"]
        assert report["degraded"]

    def test_subsystem_report_with_stats(self) -> None:
        stats = AggregatedStatistics()
        stats.record_skill("python", 100.0, True)
        report = SkillHealthReportBuilder.subsystem_report(
            registered_skills=["python"],
            active_skills=["python"],
            degraded=False,
            stats=stats,
        )
        assert report["statistics"]["total_requests"] == 1

    def test_skill_report_healthy(self) -> None:
        report = SkillHealthReportBuilder.skill_report(
            name="python",
            is_registered=True,
            is_active=True,
            healthy=True,
        )
        assert report.is_healthy
        assert report.active

    def test_skill_report_unhealthy(self) -> None:
        report = SkillHealthReportBuilder.skill_report(
            name="python",
            is_registered=True,
            is_active=False,
            healthy=False,
        )
        assert not report.is_healthy

    def test_skill_report_not_registered(self) -> None:
        report = SkillHealthReportBuilder.skill_report(
            name="python",
            is_registered=False,
            is_active=False,
            healthy=False,
        )
        assert not report.is_healthy
        assert report.registered  # unhealthy() always sets registered=True
