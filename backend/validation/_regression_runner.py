from __future__ import annotations

import copy
import logging
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.validation._types import ValidationKind, ValidationResult

_LOG = logging.getLogger("naira.validation.regression")
_PYTHON: str = sys.executable
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent


@dataclass
class BaselineRecord:
    total_tests: int
    passed: int
    failed: int
    duration_s: float
    failures: tuple[str, ...]


@dataclass
class RegressionRunner:
    baseline_file: Path = field(
        default_factory=lambda: _PROJECT_ROOT / ".regression_baseline.json"
    )
    _baseline: BaselineRecord | None = None
    _last_result: ValidationResult | None = None

    def run_full_suite(self) -> ValidationResult:
        import json
        import time

        start = time.monotonic()
        cmd = [_PYTHON, "-m", "pytest", "testing/", "-q", "--tb=short"]
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(_PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=600,
            )
        except subprocess.TimeoutExpired:
            return ValidationResult(
                kind="regression",
                name="full_suite",
                passed=False,
                duration_s=time.monotonic() - start,
                failures=("Timed out",),
                traces=(),
                logs=(),
            )

        duration = time.monotonic() - start
        passed = proc.returncode == 0

        lines = (proc.stdout or "").splitlines()
        failures: list[str] = []
        for line in lines:
            if "FAILED" in line:
                failures.append(line.strip())

        result = ValidationResult(
            kind="regression",
            name="full_suite",
            passed=passed,
            duration_s=duration,
            failures=tuple(failures),
            traces=(),
            logs=((proc.stdout or "") + (proc.stderr or ""),),
        )
        self._last_result = result

        summary_line = ""
        for line in lines:
            if "passed" in line and "failed" in line:
                summary_line = line
                break
        import re
        match = re.search(r"(\d+)\s+passed", summary_line)
        total_passed = int(match.group(1)) if match else 0
        match = re.search(r"(\d+)\s+failed", summary_line)
        total_failed = int(match.group(1)) if match else 0

        self._baseline = BaselineRecord(
            total_tests=total_passed + total_failed,
            passed=total_passed,
            failed=total_failed,
            duration_s=duration,
            failures=tuple(failures),
        )
        return result

    def save_baseline(self) -> None:
        import json

        if self._baseline is None:
            return
        data = {
            "total_tests": self._baseline.total_tests,
            "passed": self._baseline.passed,
            "failed": self._baseline.failed,
            "duration_s": self._baseline.duration_s,
            "failures": list(self._baseline.failures),
        }
        self.baseline_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        _LOG.info("Baseline saved: %d tests in %.1fs", self._baseline.total_tests, self._baseline.duration_s)

    def load_baseline(self) -> BaselineRecord | None:
        import json

        if not self.baseline_file.exists():
            return None
        try:
            data = json.loads(self.baseline_file.read_text(encoding="utf-8"))
            self._baseline = BaselineRecord(
                total_tests=data["total_tests"],
                passed=data["passed"],
                failed=data["failed"],
                duration_s=data["duration_s"],
                failures=tuple(data.get("failures", [])),
            )
            return self._baseline
        except Exception as exc:
            _LOG.warning("Failed to load baseline: %s", exc)
            return None

    def compare(self, previous: BaselineRecord, current: ValidationResult) -> str:
        lines: list[str] = []
        lines.append("Regression Comparison:")
        lines.append(f"  Previous: {previous.passed} passed, {previous.failed} failed in {previous.duration_s:.1f}s")
        lines.append(f"  Current:  {'PASS' if current.passed else 'FAIL'} in {current.duration_s:.1f}s")

        if current.failures:
            new_failures = [f for f in current.failures if f not in previous.failures]
            if new_failures:
                lines.append(f"  NEW FAILURES ({len(new_failures)}):")
                for f in new_failures:
                    lines.append(f"    - {f}")

            fixed = [f for f in previous.failures if f not in current.failures]
            if fixed:
                lines.append(f"  FIXED ({len(fixed)}):")
                for f in fixed:
                    lines.append(f"    - {f}")

        return "\n".join(lines)
