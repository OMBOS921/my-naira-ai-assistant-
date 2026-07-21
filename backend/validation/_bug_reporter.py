from __future__ import annotations

import datetime
import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from backend.validation._types import BugReport, ValidationResult

_LOG = logging.getLogger("naira.validation.bug_reporter")


@dataclass
class BugReporter:
    _bugs: list[BugReport] = field(default_factory=list)
    _known_hashes: set[str] = field(default_factory=set)

    def report(
        self,
        title: str,
        severity: Literal["critical", "high", "medium", "low"],
        file_path: str,
        description: str,
        traceback: str = "",
        logs: tuple[str, ...] = (),
        suggested_fix: str | None = None,
        line_number: int | None = None,
    ) -> BugReport:
        dedup_key = hashlib.md5(
            f"{file_path}:{line_number}:{title}".encode()
        ).hexdigest()

        if dedup_key in self._known_hashes:
            for b in self._bugs:
                if hashlib.md5(
                    f"{b.file_path}:{b.line_number}:{b.title}".encode()
                ).hexdigest() == dedup_key:
                    return b

        report = BugReport(
            id=str(uuid.uuid4())[:8],
            title=title,
            severity=severity,
            file_path=file_path,
            line_number=line_number,
            description=description,
            traceback=traceback,
            logs=logs,
            suggested_fix=suggested_fix,
            auto_fix_applied=False,
            auto_fix_success=False,
        )
        self._bugs.append(report)
        self._known_hashes.add(dedup_key)
        _LOG.warning("Bug reported: [%s] %s — %s", severity, title, file_path)
        return report

    def from_validation_result(
        self,
        result: ValidationResult,
        file_path: str = "",
    ) -> BugReport | None:
        if result.passed:
            return None
        title = f"{result.kind}/{result.name}"
        raw = "\n".join(result.failures) if result.failures else ""
        return self.report(
            title=title,
            severity="high",
            file_path=file_path,
            description=raw,
            traceback="\n".join(result.traces),
            logs=result.logs,
        )

    def mark_fix(self, bug_id: str, success: bool) -> None:
        for i, bug in enumerate(self._bugs):
            if bug.id == bug_id:
                self._bugs[i] = BugReport(
                    id=bug.id,
                    title=bug.title,
                    severity=bug.severity,
                    file_path=bug.file_path,
                    line_number=bug.line_number,
                    description=bug.description,
                    traceback=bug.traceback,
                    logs=bug.logs,
                    suggested_fix=bug.suggested_fix,
                    auto_fix_applied=True,
                    auto_fix_success=success,
                )
                break

    def summary(self) -> str:
        if not self._bugs:
            return "No bugs reported."
        critical = sum(1 for b in self._bugs if b.severity == "critical")
        high = sum(1 for b in self._bugs if b.severity == "high")
        medium = sum(1 for b in self._bugs if b.severity == "medium")
        low = sum(1 for b in self._bugs if b.severity == "low")
        fixed = sum(1 for b in self._bugs if b.auto_fix_applied and b.auto_fix_success)
        return (
            f"Bugs: {len(self._bugs)} total "
            f"({critical} critical, {high} high, {medium} medium, {low} low) "
            f"| {fixed} auto-fixed"
        )
