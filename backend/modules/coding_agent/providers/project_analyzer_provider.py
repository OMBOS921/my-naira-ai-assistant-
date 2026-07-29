from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from backend.modules.coding_agent.ports.project_analyzer_port import ProjectAnalyzerPort

_LOG = logging.getLogger("naira.coding_agent.analyzer")


class DefaultProjectAnalyzerProvider(ProjectAnalyzerPort):
    """Default provider for the Project Analyzer port.

    Analyzes project structure, dependencies, and code quality.
    """

    def __init__(
        self,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._logger = logger or _LOG
        self._available: bool = True

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def provider_name(self) -> str:
        return "default_analyzer"

    async def analyze_structure(
        self,
        path: str,
    ) -> dict[str, Any]:
        root = Path(path)
        if not root.is_dir():
            return {"root": path, "error": "Not a directory"}
        file_count = 0
        dir_count = 0
        languages: set[str] = set()
        main_files: list[str] = []
        for f in root.rglob("*"):
            if f.is_file():
                file_count += 1
                ext = f.suffix.lower()
                ext_lang_map = {
                    ".py": "python", ".js": "javascript", ".ts": "typescript",
                    ".jsx": "javascript", ".tsx": "typescript",
                    ".go": "go", ".rs": "rust", ".java": "java",
                    ".cpp": "cpp", ".c": "c", ".cs": "csharp",
                }
                if ext in ext_lang_map:
                    languages.add(ext_lang_map[ext])
                name = f.name.lower()
                if name in ("main.py", "main.go", "main.rs", "index.js", "index.ts",
                            "app.py", "app.js", "cli.py", "cli.js"):
                    main_files.append(str(f))
            elif f.is_dir():
                dir_count += 1
        return {
            "root": str(root),
            "languages": sorted(languages),
            "file_count": file_count,
            "directory_count": dir_count,
            "main_files": main_files,
            "dependencies": [],
        }

    async def analyze_dependencies(
        self,
        path: str,
        language: str,
    ) -> dict[str, Any]:
        root = Path(path)
        packages: list[str] = []
        package_manager = ""
        if language == "python":
            req_file = root / "requirements.txt"
            if req_file.exists():
                packages = [
                    line.strip()
                    for line in req_file.read_text(encoding="utf-8").splitlines()
                    if line.strip() and not line.strip().startswith("#")
                ]
                package_manager = "pip"
            pyproject = root / "pyproject.toml"
            if pyproject.exists():
                content = pyproject.read_text(encoding="utf-8")
                package_manager = "poetry" if "poetry" in content else "pip"
        elif language in ("javascript", "typescript"):
            for fname in ("package.json",):
                f = root / fname
                if f.exists():
                    package_manager = "npm"
                    break
        elif language == "go":
            f = root / "go.mod"
            if f.exists():
                package_manager = "go-mod"
                for line in f.read_text(encoding="utf-8").splitlines():
                    if line.strip().startswith("require "):
                        packages.append(line.strip())
        return {
            "packages": packages,
            "package_manager": package_manager,
            "dependency_count": len(packages),
            "version": "",
        }

    async def analyze_code_quality(
        self,
        path: str,
        language: str,
    ) -> dict[str, Any]:
        return {
            "complexity": 0.0,
            "maintainability": 1.0,
            "test_coverage": 0.0,
            "issues": [],
        }

    async def analyze_goals(
        self,
        goals: list[str],
    ) -> dict[str, Any]:
        return {
            "parsed_goals": goals,
            "required_files": [],
            "estimated_complexity": "medium",
            "subtasks": [
                {"id": f"goal_{i}", "description": g} for i, g in enumerate(goals)
            ],
        }

    async def close(self) -> None:
        self._available = False
        self._logger.info("Project analyzer provider closed")
