from __future__ import annotations

import logging
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.validation._bug_reporter import BugReporter
from backend.validation._types import ValidationResult

_LOG = logging.getLogger("naira.validation.autofix")
_PYTHON: str = sys.executable
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent


@dataclass
class AutoFixCoordinator:
    bug_reporter: BugReporter
    max_retries: int = 3
    _attempts: int = 0

    def attempt_fix(self, result: ValidationResult) -> bool:
        self._attempts += 1
        if self._attempts > self.max_retries:
            _LOG.warning("Max retries (%d) reached — giving up", self.max_retries)
            return False

        fixes: list[str] = []
        for failure in result.failures:
            fix = self._suggest_fix(failure)
            if fix:
                fixes.append(fix)

        if not fixes:
            return False

        any_success = False
        for fix_cmd in fixes:
            try:
                _LOG.info("Attempting fix: %s", fix_cmd)
                subprocess.run(
                    fix_cmd,
                    cwd=str(_PROJECT_ROOT),
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                any_success = True
            except Exception as exc:
                _LOG.warning("Fix command failed: %s — %s", fix_cmd, exc)

        return any_success

    def _suggest_fix(self, failure_line: str) -> str | None:
        lower = failure_line.lower()

        if "f401" in lower and "imported but unused" in lower:
            return f"{_PYTHON} -m ruff check --fix --select F401 backend/"

        if "i001" in lower and "import block is un-sorted" in lower:
            return f"{_PYTHON} -m ruff check --fix --select I001 backend/"

        if "e501" in lower and "line too long" in lower:
            return None

        if "f841" in lower and "local variable" in lower and "assigned" in lower:
            return f"{_PYTHON} -m ruff check --fix --select F841 backend/"

        if "sim" in lower and ("sim108" in lower or "sim102" in lower or "sim" in lower):
            return f"{_PYTHON} -m ruff check --fix --select SIM backend/"

        return None

    def reset(self) -> None:
        self._attempts = 0
