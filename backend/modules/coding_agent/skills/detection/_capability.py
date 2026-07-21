"""
Capability Detection — automatically detect project capabilities.

Detects:
- Build system
- Package manager
- Framework
- Database
- Language
- Runtime
- Test framework
- Lint system
- Formatter
- CI provider
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from backend.modules.coding_agent.skills._config import SkillConfig

_LOG = logging.getLogger("naira.coding_agent.skills.detection.capability")


class CapabilityDetector:
    """Detects project capabilities from file system contents."""

    LINT_SYSTEMS: dict[str, list[str]] = {
        "ruff": ["ruff.toml", ".ruff.toml", "pyproject.toml"],
        "flake8": [".flake8", "setup.cfg", "tox.ini"],
        "pylint": [".pylintrc", "pylintrc"],
        "eslint": [".eslintrc", ".eslintrc.js", ".eslintrc.json", ".eslintrc.yaml"],
        "prettier": [".prettierrc", ".prettierrc.json", ".prettierrc.js"],
        "black": ["pyproject.toml"],
        "isort": ["pyproject.toml", ".isort.cfg"],
        "tslint": ["tslint.json", "tslint.yaml"],
    }

    TEST_FRAMEWORKS: dict[str, list[str]] = {
        "pytest": ["pytest.ini", "pyproject.toml", "setup.cfg", "conftest.py"],
        "unittest": ["unittest"],
        "jest": ["jest.config.js", "jest.config.ts", "jest.config.json"],
        "mocha": [".mocharc.js", ".mocharc.json", ".mocharc.yml"],
        "jasmine": ["jasmine.json"],
        "vitest": ["vitest.config.js", "vitest.config.ts"],
        "junit": ["junit"],
        "googletest": ["CMakeLists.txt"],
    }

    CI_PROVIDERS: dict[str, list[str]] = {
        "github_actions": [".github/workflows/"],
        "gitlab_ci": [".gitlab-ci.yml"],
        "jenkins": ["Jenkinsfile"],
        "circleci": [".circleci/config.yml"],
        "travis": [".travis.yml"],
        "azure_devops": ["azure-pipelines.yml"],
    }

    DATABASES: dict[str, list[str]] = {
        "postgresql": ["postgres", "psycopg", "pg"],
        "mysql": ["mysql", "pymysql"],
        "mongodb": ["mongodb", "pymongo", "mongoose"],
        "sqlite": ["sqlite", "sqlite3"],
        "redis": ["redis"],
        "elasticsearch": ["elasticsearch"],
    }

    def __init__(
        self,
        *,
        config: SkillConfig | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._config = config or SkillConfig()
        self._logger = logger or _LOG

    async def detect(self, root_path: str, project_files: list[str] | None = None) -> dict[str, Any]:
        """Detect all capabilities from ``root_path``."""
        root = Path(root_path)
        if not root.is_dir():
            return {}

        files = project_files or [str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()]

        return {
            "languages": await self._detect_languages(root, files),
            "build_system": await self._detect_build_system(root, files),
            "package_manager": await self._detect_package_manager(root, files),
            "test_framework": await self._detect_test_framework(root, files),
            "lint_system": await self._detect_lint_system(root, files),
            "formatter": await self._detect_formatter(root, files),
            "ci_provider": await self._detect_ci_provider(root, files),
            "frameworks": await self._detect_frameworks(root, files),
            "databases": await self._detect_databases(root, files),
            "runtime": await self._detect_runtime(root, files),
        }

    async def _detect_languages(self, root: Path, files: list[str]) -> list[str]:
        extensions = {Path(f).suffix.lower() for f in files}
        lang_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".jsx": "javascript",
            ".java": "java",
            ".c": "c",
            ".h": "c",
            ".cpp": "cpp",
            ".hpp": "cpp",
            ".cc": "cpp",
            ".cxx": "cpp",
            ".go": "go",
            ".rs": "rust",
            ".rb": "ruby",
            ".php": "php",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
            ".cs": "csharp",
            ".sql": "sql",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".json": "json",
            ".md": "markdown",
            ".html": "html",
            ".css": "css",
            ".scss": "scss",
        }
        seen: set[str] = set()
        for ext in extensions:
            lang = lang_map.get(ext)
            if lang:
                seen.add(lang)
        return sorted(seen)

    async def _detect_build_system(self, root: Path, files: list[str]) -> str:
        indicators = {
            "pyproject.toml": "setuptools/poetry/pdm",
            "CMakeLists.txt": "cmake",
            "Makefile": "make",
            "pom.xml": "maven",
            "build.gradle": "gradle",
            "build.gradle.kts": "gradle",
            "Cargo.toml": "cargo",
            "go.mod": "go",
            "package.json": "npm/yarn/pnpm",
            "meson.build": "meson",
            "Bazel": "bazel",
        }
        for indicator, system in indicators.items():
            if indicator in files or (root / indicator).exists():
                return system
        return ""

    async def _detect_package_manager(self, root: Path, files: list[str]) -> str:
        indicators = {
            "Pipfile": "pipenv",
            "poetry.lock": "poetry",
            "pdm.lock": "pdm",
            "yarn.lock": "yarn",
            "pnpm-lock.yaml": "pnpm",
            "package-lock.json": "npm",
            "Cargo.lock": "cargo",
            "go.sum": "go",
            "Gemfile.lock": "bundler",
            "composer.lock": "composer",
        }
        for indicator, pm in indicators.items():
            if indicator in files or (root / indicator).exists():
                return pm
        return ""

    async def _detect_test_framework(self, root: Path, files: list[str]) -> str:
        file_set = set(files)
        for fw, indicators in self.TEST_FRAMEWORKS.items():
            for ind in indicators:
                if ind in file_set or (root / ind).exists():
                    return fw
        return ""

    async def _detect_lint_system(self, root: Path, files: list[str]) -> str:
        file_set = set(files)
        for lint, indicators in self.LINT_SYSTEMS.items():
            for ind in indicators:
                if ind in file_set or (root / ind).exists():
                    return lint
        return ""

    async def _detect_formatter(self, root: Path, files: list[str]) -> str:
        formatter_indicators = {
            "black": "pyproject.toml",
            "prettier": [".prettierrc", ".prettierrc.json", ".prettierrc.js"],
            "eslint": [".eslintrc", ".eslintrc.js"],
            "rustfmt": "rustfmt.toml",
            "go fmt": "",
        }
        for fmt, indicator in formatter_indicators.items():
            if isinstance(indicator, list):
                for ind in indicator:
                    if ind in files or (root / ind).exists():
                        return fmt
            elif indicator:
                if indicator in files or (root / indicator).exists():
                    return fmt
        return ""

    async def _detect_ci_provider(self, root: Path, files: list[str]) -> str:
        file_set = set(files)
        for ci, indicators in self.CI_PROVIDERS.items():
            for ind in indicators:
                if ind in file_set or (root / ind).exists():
                    return ci
        return ""

    async def _detect_frameworks(self, root: Path, files: list[str]) -> list[str]:
        frameworks: list[str] = []
        pj = root / "package.json"
        if pj.exists():
            try:
                data = json.loads(pj.read_text(encoding="utf-8", errors="replace"))
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                fw_map = {
                    "react": "react", "next": "nextjs", "express": "express",
                    "vue": "vue", "angular": "angular", "svelte": "svelte",
                    "django": "django", "fastify": "fastify", "nestjs": "nestjs",
                }
                for pkg, fw in fw_map.items():
                    if pkg in deps:
                        frameworks.append(fw)
            except Exception:
                pass
        return list(dict.fromkeys(frameworks))

    async def _detect_databases(self, root: Path, files: list[str]) -> list[str]:
        databases: list[str] = []
        for db, keywords in self.DATABASES.items():
            for f in files:
                try:
                    fp = root / f
                    if fp.is_file() and fp.stat().st_size < 1024 * 100:
                        text = fp.read_text(encoding="utf-8", errors="replace").lower()
                        if any(kw in text for kw in keywords):
                            databases.append(db)
                            break
                except Exception:
                    continue
        return databases

    async def _detect_runtime(self, root: Path, files: list[str]) -> str:
        indicators = {
            "node": "package.json",
            "python": "requirements.txt",
            "java": "pom.xml",
            "go": "go.mod",
            "rust": "Cargo.toml",
            "ruby": "Gemfile",
            "php": "composer.json",
            ".net": ".csproj",
        }
        for runtime, indicator in indicators.items():
            if indicator in files or (root / indicator).exists():
                return runtime
        return ""
