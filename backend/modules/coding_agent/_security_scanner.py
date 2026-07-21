from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

from backend.modules.coding_agent._exceptions import (
    SecurityScanError,
)

_LOG = logging.getLogger("naira.coding_agent.security_scanner")


@dataclass
class SecurityVulnerability:
    rule: str
    severity: str
    message: str
    file_path: str
    line_number: int
    snippet: str = ""
    recommendation: str = ""


@dataclass
class ScanResult:
    safe: bool
    vulnerabilities: list[SecurityVulnerability] = field(default_factory=list)
    files_scanned: int = 0
    total_issues: int = 0


_SECRET_PATTERNS: list[tuple[str, str, str]] = [
    (
        r"(?i)(?:api[_-]?key|apikey)\s*[:=]\s*['\"][^'\"]+['\"]",
        "high", "Potential API key exposed",
    ),
    (
        r"(?i)(?:secret|token|password|passwd)\s*[:=]\s*['\"][^'\"]+['\"]",
        "high", "Potential secret or credential exposed",
    ),
    (
        r"(?i)-----BEGIN\s+(?:RSA|DSA|EC|OPENSSH)\s+PRIVATE\s+KEY-----",
        "critical", "Private key detected",
    ),
    (r"(?i)ghp_[A-Za-z0-9]{36}", "critical", "GitHub personal access token detected"),
    (r"(?i)sk-[A-Za-z0-9]{32,}", "high", "OpenAI API key detected"),
    (r"(?i)AIza[0-9A-Za-z\-_]{35}", "high", "Google API key detected"),
]

_INJECTION_PATTERNS: list[tuple[str, str, str]] = [
    (r"(?:os\.system|subprocess\.call|subprocess\.Popen)\s*\(", "high", "Command injection risk"),
    (r"(?:eval|exec)\s*\(", "high", "Code execution via eval/exec"),
    (r"(?:\.\./){2,}", "medium", "Path traversal risk"),
    (r"(?:SELECT|INSERT|UPDATE|DELETE).*(?:FROM|INTO|SET)", "medium", "Possible SQL injection"),
    (r"(?i)<script[^>]*>.*?</script>", "medium", "Reflected XSS risk"),
    (r"(?:pickle\.loads|yaml\.load)\s*\(", "high", "Insecure deserialization risk"),
]

_DANGEROUS_FUNCTIONS: list[tuple[str, str, str]] = [
    (r"\bexec\b", "high", "Usage of exec() - code injection risk"),
    (r"\beval\b", "high", "Usage of eval() - code injection risk"),
    (r"\b__import__\b", "medium", "Dynamic import may lead to code injection"),
    (r"\bcompile\b", "medium", "Dynamic compilation may lead to code injection"),
]


class CodeSecurityScanner:
    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
        enabled: bool = True,
        rules: tuple[str, ...] | None = None,
    ) -> None:
        self._logger = logger or _LOG
        self._enabled = enabled
        self._rules = rules or ("secrets", "injection", "xss", "path_traversal")
        self._total_scans = 0
        self._total_issues_found = 0
        self._degraded = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def degraded(self) -> bool:
        return self._degraded

    def degrade(self) -> None:
        self._degraded = True
        self._logger.warning("CodeSecurityScanner marked degraded")

    async def scan_file(self, file_path: str) -> ScanResult:
        if not self._enabled or self._degraded:
            return ScanResult(safe=True)

        self._total_scans += 1
        try:
            if not os.path.isfile(file_path):
                return ScanResult(safe=True)
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            return self._scan_content(content, file_path)
        except (OSError, PermissionError) as exc:
            self._logger.warning("Cannot scan %s: %s", file_path, exc)
            return ScanResult(safe=True)

    async def scan_code(self, code: str, source: str = "<inline>") -> ScanResult:
        if not self._enabled or self._degraded:
            return ScanResult(safe=True)
        self._total_scans += 1
        return self._scan_content(code, source)

    async def scan_project(self, project_path: str) -> ScanResult:
        if not self._enabled or self._degraded:
            return ScanResult(safe=True)

        self._total_scans += 1
        all_vulns: list[SecurityVulnerability] = []
        files_scanned = 0

        try:
            for root, _dirs, files in os.walk(project_path):
                _dirs[:] = [d for d in _dirs if not d.startswith(".") and d != "__pycache__"]
                for filename in files:
                    if not self._should_scan_file(filename):
                        continue
                    file_path = os.path.join(root, filename)
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                            content = f.read()
                        result = self._scan_content(content, file_path)
                        all_vulns.extend(result.vulnerabilities)
                        files_scanned += 1
                    except (OSError, PermissionError):
                        continue
        except OSError as exc:
            raise SecurityScanError(
                f"Failed to scan project: {exc}",
                context={"project_path": project_path},
            ) from exc

        self._total_issues_found += len(all_vulns)
        safe = len(all_vulns) == 0
        return ScanResult(
            safe=safe,
            vulnerabilities=all_vulns,
            files_scanned=files_scanned,
            total_issues=len(all_vulns),
        )

    def _should_scan_file(self, filename: str) -> bool:
        ext = os.path.splitext(filename)[1].lower()
        return ext in (
            ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".rb",
            ".php", ".c", ".cpp", ".h", ".hpp", ".cs", ".swift", ".kt",
            ".sh", ".bash", ".ps1", ".yaml", ".yml", ".json", ".env",
            ".cfg", ".conf", ".ini", ".txt", ".md",
        )

    def _scan_content(
        self, content: str, file_path: str,
    ) -> ScanResult:
        vulnerabilities: list[SecurityVulnerability] = []
        lines = content.split("\n")

        if "secrets" in self._rules:
            for pattern, severity, message in _SECRET_PATTERNS:
                for match in re.finditer(pattern, content):
                    line_num = content[:match.start()].count("\n") + 1
                    snippet = lines[line_num - 1].strip() if line_num <= len(lines) else ""
                    vulnerabilities.append(SecurityVulnerability(
                        rule="secrets",
                        severity=severity,
                        message=message,
                        file_path=file_path,
                        line_number=line_num,
                        snippet=snippet[:100],
                        recommendation=(
                            "Remove or rotate the exposed "
                            f"{message.split()[-1].lower()}"
                        ),
                    ))

        if "injection" in self._rules:
            for pattern, severity, message in _INJECTION_PATTERNS:
                for match in re.finditer(pattern, content):
                    line_num = content[:match.start()].count("\n") + 1
                    snippet = lines[line_num - 1].strip() if line_num <= len(lines) else ""
                    vulnerabilities.append(SecurityVulnerability(
                        rule="injection",
                        severity=severity,
                        message=message,
                        file_path=file_path,
                        line_number=line_num,
                        snippet=snippet[:100],
                        recommendation=f"Review and sanitize the {message.lower()}",
                    ))

        if "xss" in self._rules:
            for pattern, severity, message in _DANGEROUS_FUNCTIONS:
                for match in re.finditer(pattern, content):
                    line_num = content[:match.start()].count("\n") + 1
                    snippet = lines[line_num - 1].strip() if line_num <= len(lines) else ""
                    vulnerabilities.append(SecurityVulnerability(
                        rule="xss",
                        severity=severity,
                        message=message,
                        file_path=file_path,
                        line_number=line_num,
                        snippet=snippet[:100],
                        recommendation=f"Avoid using {match.group()} if possible",
                    ))

        self._total_issues_found += len(vulnerabilities)
        return ScanResult(
            safe=len(vulnerabilities) == 0,
            vulnerabilities=vulnerabilities,
            files_scanned=1,
            total_issues=len(vulnerabilities),
        )

    def metrics(self) -> dict[str, Any]:
        return {
            "enabled": self._enabled,
            "degraded": self._degraded,
            "total_scans": self._total_scans,
            "total_issues_found": self._total_issues_found,
            "rules_active": list(self._rules),
        }

    async def health_check(self) -> bool:
        return self._enabled and not self._degraded
