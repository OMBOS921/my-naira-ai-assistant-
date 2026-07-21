from __future__ import annotations

import io
import os
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.validation._types import ValidationKind, ValidationResult

_PYTHON: str = sys.executable
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent


@dataclass
class ValidationRunner:
    kind: ValidationKind
    name: str
    test_paths: tuple[str, ...] = ()
    pytest_args: tuple[str, ...] = (
        "-x",
        "-q",
        "--tb=short",
        "--no-header",
    )
    timeout_s: float = 180.0
    env_overrides: dict[str, str] = field(default_factory=dict)
    _last_stdout: str = ""
    _last_stderr: str = ""
    _last_returncode: int = -1

    def run(self) -> ValidationResult:
        start = time.monotonic()
        cmd = [
            _PYTHON,
            "-m",
            "pytest",
            *self.pytest_args,
            *self.test_paths,
        ]
        env = {**os.environ, **self.env_overrides}

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(_PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                env=env,
            )
        except subprocess.TimeoutExpired:
            duration = time.monotonic() - start
            return ValidationResult(
                kind=self.kind,
                name=self.name,
                passed=False,
                duration_s=duration,
                failures=(f"Timed out after {self.timeout_s}s",),
                traces=(),
                logs=(),
            )
        except Exception as exc:
            duration = time.monotonic() - start
            return ValidationResult(
                kind=self.kind,
                name=self.name,
                passed=False,
                duration_s=duration,
                failures=(str(exc),),
                traces=(traceback.format_exc(),),
                logs=(),
            )

        duration = time.monotonic() - start
        self._last_stdout = proc.stdout
        self._last_stderr = proc.stderr
        self._last_returncode = proc.returncode

        passed = proc.returncode == 0
        lines = (proc.stdout or "").splitlines()
        failures: list[str] = []
        traces: list[str] = []
        logs: list[str] = [(proc.stdout or ""), (proc.stderr or "")]
        for line in lines:
            if "FAILED" in line:
                failures.append(line.strip())
            if "ERROR" in line and "FAILED" not in line:
                failures.append(line.strip())
            if "Warning" in line or "warning" in line:
                logs.append(line.strip())

        summary_lines = [l for l in lines if "passed" in l and "failed" in l]
        if not summary_lines and proc.stdout:
            summary_lines = lines[-3:]

        return ValidationResult(
            kind=self.kind,
            name=self.name,
            passed=passed,
            duration_s=duration,
            failures=tuple(failures),
            traces=tuple(traces),
            logs=tuple(logs + summary_lines),
        )

    def run_repeated(
        self,
        count: int = 5,
        settle_time_s: float = 0.1,
    ) -> list[ValidationResult]:
        results: list[ValidationResult] = []
        for i in range(count):
            result = self.run()
            results.append(result)
            time.sleep(settle_time_s)
        return results
