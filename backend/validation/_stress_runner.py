from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from backend.validation._runner import ValidationRunner
from backend.validation._types import ValidationKind, ValidationResult

_LOG = logging.getLogger("naira.validation.stress")


@dataclass
class StressRunner:
    runner_factory: Callable[[], ValidationRunner]
    iterations: int = 20
    settle_time_s: float = 0.2
    _results: list[list[ValidationResult]] = field(default_factory=list)

    def run_stress(self) -> list[ValidationResult]:
        all_results: list[ValidationResult] = []
        failures: list[ValidationResult] = []

        for i in range(self.iterations):
            runner = self.runner_factory()
            result = runner.run()
            all_results.append(result)
            if not result.passed:
                failures.append(result)
            time.sleep(self.settle_time_s + random.uniform(0, 0.1))

        self._results.append(all_results)
        return all_results

    def run_cold_start_stress(self, module_names: list[str]) -> list[ValidationResult]:
        results: list[ValidationResult] = []
        for i in range(min(self.iterations, 10)):
            import gc
            gc.collect()
            imported: list[str] = []
            errors: list[str] = []
            for mod_name in module_names:
                try:
                    import importlib
                    importlib.import_module(mod_name)
                    imported.append(mod_name)
                except Exception as exc:
                    errors.append(f"{mod_name}: {exc}")
            passed = len(errors) == 0
            results.append(
                ValidationResult(
                    kind="stress",
                    name=f"cold_start_{i}",
                    passed=passed,
                    duration_s=0.0,
                    failures=tuple(errors),
                    traces=(),
                    logs=(f"Imported {len(imported)} modules",),
                )
            )
            time.sleep(self.settle_time_s)
        return results

    @property
    def flaky_failures(self) -> list[ValidationResult]:
        seen: dict[str, int] = {}
        for batch in self._results:
            for r in batch:
                key = f"{r.kind}/{r.name}"
                if not r.passed:
                    seen[key] = seen.get(key, 0) + 1
        flaky = [
            r for batch in self._results for r in batch
            if not r.passed and seen.get(f"{r.kind}/{r.name}", 0) < len(self._results)
        ]
        return flaky

    def stability_score(self) -> float:
        total = sum(len(batch) for batch in self._results)
        passed = sum(
            1 for batch in self._results for r in batch if r.passed
        )
        if total == 0:
            return 1.0
        return passed / total
