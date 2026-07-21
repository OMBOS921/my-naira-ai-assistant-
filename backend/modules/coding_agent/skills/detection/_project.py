"""
Project Detection — automatically detect project types.

Detects:
- Python Project
- React Project
- Node Project
- Next Project
- Java Project
- C Project
- C++ Project
- Docker Project
- Kubernetes Project
- Monorepo
- Mixed Repository
"""

from __future__ import annotations

import logging
from pathlib import Path

from backend.modules.coding_agent.skills._config import SkillConfig
from backend.modules.coding_agent.skills.context._models import ProjectContext

_LOG = logging.getLogger("naira.coding_agent.skills.detection.project")


class ProjectDetector:
    """Detects project type and configuration from file system."""

    PATTERNS: dict[str, list[str]] = {
        "python": ["setup.py", "setup.cfg", "pyproject.toml", "requirements.txt", "Pipfile", "tox.ini"],
        "node": ["package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"],
        "react": ["src/App.js", "src/App.tsx", "jsconfig.json", "tsconfig.json"],
        "next": ["next.config.js", "next.config.mjs", "next.config.ts"],
        "java": ["pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle"],
        "c": ["Makefile", "CMakeLists.txt", "configure.ac"],
        "cpp": ["CMakeLists.txt", "Makefile", "conanfile.txt", "vcpkg.json"],
        "docker": ["Dockerfile", "docker-compose.yml", "docker-compose.yaml", ".dockerignore"],
        "kubernetes": ["k8s/", "kubernetes/", "deploy/"],
        "monorepo": ["lerna.json", "nx.json", "turbo.json", "pnpm-workspace.yaml"],
    }

    def __init__(
        self,
        *,
        config: SkillConfig | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._config = config or SkillConfig()
        self._logger = logger or _LOG

    async def detect(self, root_path: str) -> ProjectContext:
        """Detect project type and characteristics from ``root_path``."""
        root = Path(root_path)
        if not root.is_dir():
            self._logger.warning("Project root not found: %s", root_path)
            return ProjectContext(root_path=root_path, project_type="unknown")

        found_types: list[str] = []
        detected_frameworks: list[str] = []
        detected_languages: list[str] = []
        build_system = ""
        package_manager = ""

        for proj_type, indicators in self.PATTERNS.items():
            for indicator in indicators:
                candidate = root / indicator
                if candidate.exists():
                    if proj_type not in found_types:
                        found_types.append(proj_type)
                    break

        if "python" in found_types:
            detected_languages.append("python")
            pw = root / "pyproject.toml"
            if pw.exists():
                build_system = "setuptools"
                pkg_text = pw.read_text(encoding="utf-8", errors="replace")
                if "[build-system]" in pkg_text:
                    if "poetry" in pkg_text:
                        build_system = "poetry"
                    elif "flit" in pkg_text:
                        build_system = "flit"
                    elif "pdm" in pkg_text:
                        build_system = "pdm"
                package_manager = self._detect_python_pkg(root)

        if "node" in found_types or "react" in found_types or "next" in found_types:
            detected_languages.append("javascript")
            pj = root / "package.json"
            if pj.exists():
                deps = pj.read_text(encoding="utf-8", errors="replace")
                build_system, package_manager = self._detect_node_build(deps)
                if not build_system:
                    if "typescript" in deps.lower():
                        build_system = "tsc"
                    else:
                        build_system = "npm"

        if "java" in found_types:
            detected_languages.append("java")
            if (root / "pom.xml").exists():
                build_system = "maven"
            elif any((root / f).exists() for f in ["build.gradle", "build.gradle.kts"]):
                build_system = "gradle"

        if "c" in found_types:
            detected_languages.append("c")
            if (root / "CMakeLists.txt").exists():
                build_system = "cmake"
            elif (root / "Makefile").exists():
                build_system = "make"

        if "cpp" in found_types:
            detected_languages.append("cpp")
            if not build_system:
                if (root / "CMakeLists.txt").exists():
                    build_system = "cmake"
                elif (root / "Makefile").exists():
                    build_system = "make"

        detected_frameworks = self._detect_frameworks(root, found_types)

        file_count = sum(1 for _ in root.rglob("*") if _.is_file()) if root.exists() else 0
        dir_count = sum(1 for _ in root.rglob("*") if _.is_dir()) if root.exists() else 0
        is_monorepo = "monorepo" in found_types

        project_type = self._resolve_project_type(found_types)
        languages = list(dict.fromkeys(detected_languages))

        return ProjectContext(
            root_path=str(root.resolve()),
            project_type=project_type,
            languages=languages,
            frameworks=detected_frameworks,
            build_system=build_system,
            package_manager=package_manager,
            is_monorepo=is_monorepo,
            file_count=file_count,
            directory_count=dir_count,
            raw={"found_types": found_types, "indicators_matched": found_types},
        )

    def _resolve_project_type(self, found_types: list[str]) -> str:
        if len(found_types) > 2:
            return "mixed"
        if "monorepo" in found_types:
            return "monorepo"
        if "next" in found_types:
            return "next"
        if "react" in found_types:
            return "react"
        if "python" in found_types:
            return "python"
        if "node" in found_types:
            return "node"
        if "java" in found_types:
            return "java"
        if "cpp" in found_types:
            return "cpp"
        if "c" in found_types:
            return "c"
        if "docker" in found_types:
            return "docker"
        if "kubernetes" in found_types:
            return "kubernetes"
        return "unknown"

    def _detect_python_pkg(self, root: Path) -> str:
        if (root / "Pipfile").exists():
            return "pipenv"
        if (root / "poetry.lock").exists():
            return "poetry"
        if (root / "pdm.lock").exists():
            return "pdm"
        if (root / "requirements.txt").exists():
            return "pip"
        return ""

    def _detect_node_build(self, deps: str) -> tuple[str, str]:
        pm = ""
        bd = ""
        lower = deps.lower()
        if '"next' in lower:
            bd = "next"
        elif '"react' in lower:
            bd = "react-scripts"
        elif '"vite' in lower:
            bd = "vite"
        elif '"webpack' in lower:
            bd = "webpack"
        if 'yarn' in deps or (Path(root := Path(".")) / "yarn.lock").exists():
            pm = "yarn"
        elif 'pnpm' in deps or (Path(".") / "pnpm-lock.yaml").exists():
            pm = "pnpm"
        else:
            pm = "npm"
        return bd, pm

    def _detect_frameworks(self, root: Path, found_types: list[str]) -> list[str]:
        frameworks: list[str] = []
        if "react" in found_types:
            frameworks.append("react")
        if "next" in found_types:
            frameworks.append("nextjs")
        if "python" in found_types:
            pyproject = root / "pyproject.toml"
            if pyproject.exists():
                text = pyproject.read_text(encoding="utf-8", errors="replace").lower()
                if "django" in text:
                    frameworks.append("django")
                if "fastapi" in text:
                    frameworks.append("fastapi")
                if "flask" in text:
                    frameworks.append("flask")
        if "java" in found_types:
            pom = root / "pom.xml"
            if pom.exists():
                text = pom.read_text(encoding="utf-8", errors="replace").lower()
                if "spring" in text:
                    frameworks.append("spring")
        return frameworks
