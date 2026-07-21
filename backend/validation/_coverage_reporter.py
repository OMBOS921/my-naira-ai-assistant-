from __future__ import annotations

import json
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.validation._types import CoverageData

_LOG = logging.getLogger("naira.validation.coverage")
_PYTHON: str = sys.executable
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent


@dataclass
class CoverageReporter:
    test_paths: tuple[str, ...] = ("testing/",)
    source_paths: tuple[str, ...] = ("backend/",)
    _last_json: dict[str, Any] = field(default_factory=dict)

    def measure(self) -> CoverageData | None:
        cov_path = _PROJECT_ROOT / ".coverage"
        if cov_path.exists():
            cov_path.unlink()

        cmd = [
            _PYTHON,
            "-m",
            "coverage",
            "run",
            f"--source={','.join(self.source_paths)}",
            "-m",
            "pytest",
            *self.test_paths,
            "--tb=short",
            "-q",
        ]

        try:
            subprocess.run(
                cmd,
                cwd=str(_PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=300,
            )
        except subprocess.TimeoutExpired:
            _LOG.warning("Coverage measurement timed out")
            return None
        except Exception as exc:
            _LOG.warning("Coverage measurement failed: %s", exc)
            return None

        report_cmd = [
            _PYTHON,
            "-m",
            "coverage",
            "json",
            "-o",
            "-",
        ]
        try:
            result = subprocess.run(
                report_cmd,
                cwd=str(_PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=30,
            )
            data = json.loads(result.stdout)
        except Exception as exc:
            _LOG.warning("Failed to parse coverage JSON: %s", exc)
            return None

        self._last_json = data
        totals = data.get("totals", {})
        files_data = data.get("files", {})

        per_module: dict[str, float] = {}
        for filepath, fdata in files_data.items():
            fsummary = fdata.get("summary", {})
            total_lines = fsummary.get("num_statements", 0)
            covered = fsummary.get("covered_lines", 0)
            if total_lines > 0:
                per_module[filepath] = (covered / total_lines) * 100.0

        return CoverageData(
            lines_total=totals.get("num_statements", 0),
            lines_covered=totals.get("covered_lines", 0),
            branches_total=totals.get("num_branches", 0),
            branches_covered=totals.get("covered_branches", 0),
            coverage_pct=totals.get("percent_covered_display", 0.0),
            per_module=per_module,
        )
