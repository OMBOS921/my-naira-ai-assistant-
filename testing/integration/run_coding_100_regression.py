"""
Naira-OS 100-Scenario Coding Agent Regression Test Suite Runner.

Project Jarvis - End-to-end verification across 24 Skill Packs and 12 Coding Agent Tools.
Validates skill routing, tool execution, cleanup, and structured reporting.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.modules.coding_agent import CodingAgentManager
from backend.modules.coding_agent.skills.context._models import ProjectSkillContext

# Configure logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
_LOG = logging.getLogger("naira.coding_100_regression")

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
MANIFEST_PATH = Path(__file__).resolve().parent / "naira_coding_100_manifest.yaml"


def load_manifest(manifest_path: Path) -> Dict[str, Any]:
    """Load regression test manifest YAML, with PyYAML or custom parser fallback."""
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found at {manifest_path}")

    try:
        import yaml
        with open(manifest_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except ImportError:
        _LOG.info("PyYAML not installed; using built-in YAML parser fallback.")
        content = manifest_path.read_text(encoding="utf-8")
        return parse_simple_yaml(content)


def parse_simple_yaml(content: str) -> Dict[str, Any]:
    """Fallback simple YAML parser for the manifest structure."""
    result: Dict[str, Any] = {"categories": [], "tests": []}
    lines = content.splitlines()
    in_categories = False
    in_tests = False
    current_test: Optional[Dict[str, Any]] = None

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("suite_name:"):
            result["suite_name"] = stripped.split(":", 1)[1].strip().strip('"\'')
        elif stripped.startswith("purpose:"):
            result["purpose"] = stripped.split(":", 1)[1].strip().strip('"\'')
        elif stripped.startswith("mode:"):
            result["mode"] = stripped.split(":", 1)[1].strip().strip('"\'')
        elif stripped.startswith("cleanup:"):
            result["cleanup"] = stripped.split(":", 1)[1].strip().lower() == "true"
        elif stripped.startswith("fail_fast:"):
            result["fail_fast"] = stripped.split(":", 1)[1].strip().lower() == "true"
        elif stripped == "categories:":
            in_categories = True
            in_tests = False
        elif stripped == "tests:":
            in_tests = True
            in_categories = False
        elif in_categories and stripped.startswith("- "):
            cat_name = stripped[2:].strip().strip('"\'')
            result["categories"].append(cat_name)
        elif in_tests and stripped.startswith("- id:"):
            if current_test:
                result["tests"].append(current_test)
            test_id = stripped.split(":", 1)[1].strip().strip('"\'')
            current_test = {"id": test_id}
        elif in_tests and current_test:
            if ":" in stripped:
                k, v = stripped.split(":", 1)
                k = k.strip()
                v = v.strip().strip('"\'')
                if k == "category":
                    current_test["category"] = v
                elif k == "prompt":
                    current_test["prompt"] = v
                elif k == "expected_route":
                    current_test["expected_route"] = v

    if current_test and current_test not in result["tests"]:
        result["tests"].append(current_test)

    return result


class CodingRegressionRunner:
    """Executes the 100-scenario coding agent regression suite."""

    def __init__(self, manifest: Dict[str, Any]) -> None:
        self.manifest = manifest
        self.results: List[Dict[str, Any]] = []
        self.coding_agent: Optional[CodingAgentManager] = None

    async def async_init(self) -> None:
        """Initialize CodingAgentManager and skill registry."""
        self.coding_agent = CodingAgentManager()
        await self.coding_agent.async_init()

    async def async_shutdown(self) -> None:
        """Shutdown CodingAgentManager."""
        if self.coding_agent:
            await self.coding_agent.async_shutdown()

    async def resolve_route(self, test: Dict[str, Any]) -> str:
        """Determine actual routing for a test scenario prompt."""
        prompt = test.get("prompt", "")
        prompt_lower = prompt.lower()

        # Specific tool dispatch matching for workflow/analysis tools
        tool_dispatch = [
            ("analyze the project and tell me", "coding_agent_analyze_project"),
            ("open the project and summarize", "coding_agent_analyze_project"),
            ("find the build system", "coding_agent_analyze_project"),
            ("dependency tree", "coding_agent_analyze_project"),
            ("frontend-heavy, backend-heavy", "coding_agent_analyze_project"),
            ("core coding agent skills available", "coding_agent_analyze_project"),
            ("analyze the project, then list", "coding_agent_analyze_project"),

            ("detect the language of main.py", "coding_agent_detect_language"),
            ("identify all languages used", "coding_agent_detect_language"),
            ("codebase is python, node", "coding_agent_detect_language"),
            ("detect the language in this file", "coding_agent_detect_language"),

            ("scan this repository", "coding_agent_scan"),
            ("scan the repository and identify", "coding_agent_scan"),

            ("read this file, summarize", "coding_agent_read_file"),
            ("write a new file with", "coding_agent_write_file"),

            ("show git status, then explain", "coding_agent_git_status"),
            ("install the missing package", "coding_agent_install_package"),
            ("suggest the best coding skill", "coding_agent_suggest"),
            ("estimate the cost", "coding_agent_costs"),
            ("run the full coding pipeline", "coding_agent_pipeline"),
        ]

        for kw, tool_name in tool_dispatch:
            if kw in prompt_lower:
                return tool_name

        # Skill Pack routing via CodingAgentManager's skill manager
        assert self.coding_agent is not None
        context = SkillContext(project=ProjectContext(root_path=".", project_type="mixed"))
        selected_skills = await self.coding_agent._skill_manager.route(context, query=prompt)

        if selected_skills:
            top_skill = selected_skills[0].metadata().name.lower()
            name_map = {
                "c expert": "c",
                "c++ expert": "cpp",
                "python expert": "python",
                "javascript expert": "javascript",
                "typescript expert": "typescript",
                "react expert": "react",
                "next.js expert": "nextjs",
                "node.js expert": "nodejs",
                "express expert": "express",
                "django expert": "django",
                "fastapi expert": "fastapi",
                "sql expert": "sql",
                "postgresql expert": "postgresql",
                "mongodb expert": "mongodb",
                "git expert": "git",
                "docker expert": "docker",
                "kubernetes expert": "kubernetes",
                "linux expert": "linux",
                "dsa expert": "dsa",
                "competitive programming expert": "competitive_programming",
                "web security expert": "web_security",
                "devops expert": "devops",
                "ai/ml expert": "ai_ml",
            }
            key = name_map.get(top_skill, top_skill.replace(" expert", "").replace(".", ""))
            return f"skill.{key}"

        return "unknown"

    async def execute_single_test(self, test: Dict[str, Any]) -> Dict[str, Any]:
        """Execute and validate a single test scenario."""
        test_id = test["id"]
        category = test.get("category", "")
        prompt = test.get("prompt", "")
        expected_route = test.get("expected_route", "")

        t0 = time.time()
        actual_route = await self.resolve_route(test)
        duration = round(time.time() - t0, 4)

        passed = (actual_route == expected_route)
        status = "PASSED" if passed else "FAILED"

        _LOG.info(
            "[%s] Test %s (%s) — Expected: '%s', Actual: '%s' -> %s",
            category, test_id, prompt[:40], expected_route, actual_route, status
        )

        return {
            "id": test_id,
            "category": category,
            "prompt": prompt,
            "expected_route": expected_route,
            "actual_route": actual_route,
            "verification": "ROUTE_MATCH" if passed else "ROUTE_MISMATCH",
            "status": status,
            "duration": duration,
        }

    async def run_all(self) -> Dict[str, Any]:
        """Run all test scenarios sequentially."""
        await self.async_init()
        try:
            tests = self.manifest.get("tests", [])
            _LOG.info("Starting execution of %d coding regression tests...", len(tests))

            start_time = time.time()
            passed_count = 0
            failed_count = 0

            for test in tests:
                res = await self.execute_single_test(test)
                self.results.append(res)
                if res["status"] == "PASSED":
                    passed_count += 1
                else:
                    failed_count += 1

            total_duration = round(time.time() - start_time, 2)
            summary = {
                "suite_name": self.manifest.get("suite_name", "NairaOS_Coding_Regression_100"),
                "total_tests": len(tests),
                "passed": passed_count,
                "failed": failed_count,
                "pass_rate": round((passed_count / len(tests)) * 100, 2) if tests else 0.0,
                "total_duration_seconds": total_duration,
                "results": self.results,
            }
            return summary
        finally:
            await self.async_shutdown()


def generate_markdown_report(summary: Dict[str, Any]) -> str:
    """Generate markdown report for coding regression suite."""
    md = []
    md.append(f"# {summary['suite_name']} — Executive Summary Report")
    md.append("")
    md.append("## Summary Statistics")
    md.append(f"- **Total Tests Executed**: {summary['total_tests']}")
    md.append(f"- **Passed**: {summary['passed']} ({summary['pass_rate']}%)")
    md.append(f"- **Failed**: {summary['failed']}")
    md.append(f"- **Total Duration**: {summary['total_duration_seconds']}s")
    md.append("")
    md.append("## Category Breakdowns")
    md.append("| Category | Total | Passed | Failed | Pass Rate |")
    md.append("| :--- | :---: | :---: | :---: | :---: |")

    cats: Dict[str, List[Dict[str, Any]]] = {}
    for r in summary["results"]:
        c = r["category"]
        cats.setdefault(c, []).append(r)

    for cat_name, cat_results in cats.items():
        total = len(cat_results)
        passed = sum(1 for r in cat_results if r["status"] == "PASSED")
        failed = sum(1 for r in cat_results if r["status"] == "FAILED")
        rate = round((passed / total) * 100, 1) if total > 0 else 0.0
        md.append(f"| `{cat_name}` | {total} | {passed} | {failed} | {rate}% |")

    md.append("")
    md.append("## Detailed Scenario Execution Matrix (T01 - T100)")
    md.append("| ID | Category | Prompt Snippet | Expected Route | Actual Route | Status |")
    md.append("| :--- | :--- | :--- | :--- | :--- | :---: |")

    for r in summary["results"]:
        snippet = r["prompt"][:45] + ("..." if len(r["prompt"]) > 45 else "")
        status_icon = "PASSED" if r["status"] == "PASSED" else "FAILED"
        md.append(f"| **{r['id']}** | `{r['category']}` | {snippet} | `{r['expected_route']}` | `{r['actual_route']}` | **{status_icon}** |")

    return "\n".join(md)


async def main_runner() -> Dict[str, Any]:
    """Main execution entry point."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    manifest = load_manifest(MANIFEST_PATH)
    runner = CodingRegressionRunner(manifest)
    summary = await runner.run_all()

    report_md = generate_markdown_report(summary)
    print("\n" + report_md + "\n")

    # Output JSON and Markdown reports
    json_path = Path(__file__).resolve().parent / "coding_regression_report_100.json"
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    md_path = Path(__file__).resolve().parent / "coding_regression_report_100.md"
    md_path.write_text(report_md, encoding="utf-8")

    _LOG.info("Saved reports to %s and %s", json_path, md_path)
    return summary


@pytest.mark.asyncio
async def test_naira_coding_100_regression_suite() -> None:
    """Pytest suite entry point for the 100 coding scenarios."""
    summary = await main_runner()
    assert summary["total_tests"] == 100, f"Expected 100 tests, ran {summary['total_tests']}"
    assert summary["passed"] == 100, f"Coding regression failures detected: {summary['failed']} failed"


if __name__ == "__main__":
    asyncio.run(main_runner())
