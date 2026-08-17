"""
Skill Router — automatic skill selection based on file and project context.

Examples:
- Python file → Python Skill
- React component → React Skill
- Dockerfile → Docker Skill
- SQL migration → SQL Skill
- Mixed project → Multiple skills cooperate.
"""

from __future__ import annotations

import logging
from pathlib import Path
import re

from backend.modules.coding_agent.skills._config import SkillConfig
from backend.modules.coding_agent.skills._registry import SkillRegistry
from backend.modules.coding_agent.skills._skill_port import SkillPort
from backend.modules.coding_agent.skills.context._models import ProjectSkillContext

_LOG = logging.getLogger("naira.coding_agent.skills.routing")


class SkillRouter:
    """Routes requests to appropriate Skill Packs based on context."""

    FILENAME_ROUTES: dict[str, list[str]] = {
        "Dockerfile": ["docker"],
        "docker-compose.yml": ["docker"],
        "docker-compose.yaml": ["docker"],
        "package.json": ["nodejs", "javascript", "typescript"],
        "pyproject.toml": ["python"],
        "requirements.txt": ["python"],
        "Pipfile": ["python"],
        "pom.xml": ["java"],
        "build.gradle": ["java"],
        "build.gradle.kts": ["java"],
        "CMakeLists.txt": ["cpp", "c"],
        "Makefile": ["c", "cpp", "python"],
        "tsconfig.json": ["typescript"],
        "next.config.js": ["nextjs"],
        "next.config.mjs": ["nextjs"],
        "next.config.ts": ["nextjs"],
        "Dockerfile.*": ["docker"],
        "*.tf": ["devops", "kubernetes"],
        "k8s/*.yaml": ["kubernetes"],
        "*.sql": ["sql", "postgresql", "mongodb"],
        ".gitignore": ["git"],
        ".gitmodules": ["git"],
        ".github/workflows/*.yml": ["devops", "git"],
    }

    EXTENSION_ROUTES: dict[str, list[str]] = {
        ".py": ["python"],
        ".js": ["javascript", "nodejs"],
        ".jsx": ["react", "javascript"],
        ".ts": ["typescript", "nodejs"],
        ".tsx": ["react", "typescript", "nextjs"],
        ".java": ["java"],
        ".c": ["c"],
        ".h": ["c", "cpp"],
        ".cpp": ["cpp"],
        ".hpp": ["cpp"],
        ".cc": ["cpp"],
        ".cxx": ["cpp"],
        ".sql": ["sql", "postgresql"],
        ".json": [],
        ".yaml": ["devops", "kubernetes"],
        ".yml": ["devops", "kubernetes"],
        ".tf": ["devops"],
        ".tfvars": ["devops"],
        ".dockerignore": ["docker"],
        ".gitkeep": [],
        ".md": [],
    }

    QUERY_ROUTES: dict[str, list[str]] = {
        "c++": ["cpp"],
        "cpp": ["cpp"],
        "smart pointer": ["cpp"],
        "raii": ["cpp"],
        "template compilation": ["cpp"],
        "binary search": ["cpp"],
        "c program": ["c"],
        "pointer arithmetic in c": ["c"],
        "scanf": ["c"],
        "segmentation fault": ["c"],
        "matrix multiplication": ["c"],
        "python": ["python"],
        "json file": ["python"],
        "remove duplicates": ["python"],
        "decorators": ["python"],
        "type hints": ["python"],
        "dataclasses": ["python"],
        "scrape": ["python"],
        "argparse": ["python"],
        "traceback": ["python"],
        "calculator function": ["python"],
        "loop that is too slow": ["python"],
        "debounce": ["javascript"],
        "async/await": ["javascript"],
        "event loop": ["javascript"],
        "es6": ["javascript"],
        "js script": ["javascript"],
        "typescript interface": ["typescript"],
        "type mismatch": ["typescript"],
        "generics in typescript": ["typescript"],
        "utility type": ["typescript"],
        "to typescript": ["typescript"],
        "typescript": ["typescript"],
        "react counter": ["react"],
        "state update bug": ["react"],
        "difference between react": ["react"],
        "memoization": ["react"],
        "react": ["react"],
        "next.js page": ["nextjs"],
        "next.js api route": ["nextjs"],
        "next.js": ["nextjs"],
        "nextjs": ["nextjs"],
        "express route": ["express"],
        "express middleware": ["express"],
        "express": ["express"],
        "node.js script": ["nodejs"],
        "node.js function": ["nodejs"],
        "node.js": ["nodejs"],
        "nodejs": ["nodejs"],
        "django model": ["django"],
        "django migration": ["django"],
        "django view": ["django"],
        "django orm": ["django"],
        "class-based views": ["django"],
        "django": ["django"],
        "fastapi endpoint": ["fastapi"],
        "fastapi dependency": ["fastapi"],
        "fastapi route": ["fastapi"],
        "fastapi": ["fastapi"],
        "pydantic": ["fastapi"],
        "testclient": ["fastapi"],
        "sql query": ["sql"],
        "duplicate rows": ["sql"],
        "sql joins": ["sql"],
        "nested subqueries": ["sql"],
        "sql schema": ["sql"],
        "connection string": ["sql"],
        "sql": ["sql"],
        "postgresql query": ["postgresql"],
        "database column": ["postgresql"],
        "indexing strategy": ["postgresql"],
        "postgresql": ["postgresql"],
        "mongodb schema": ["mongodb"],
        "mongodb aggregation": ["mongodb"],
        "mongodb": ["mongodb"],
        "git status": ["git"],
        "commit message": ["git"],
        "merge conflict": ["git"],
        "git": ["git"],
        "dockerfile": ["docker"],
        "docker image": ["docker"],
        "docker-compose": ["docker"],
        "docker": ["docker"],
        "linux file permissions": ["linux"],
        "find large files": ["linux"],
        "linux": ["linux"],
        "ci/cd workflow": ["devops"],
        "kubernetes": ["kubernetes"],
        "xss": ["web_security"],
        "csrf": ["web_security"],
        "owasp": ["web_security"],
        "password hashing": ["web_security"],
        "command injection": ["web_security"],
        "web security": ["web_security"],
        "dsa problem": ["dsa"],
        "dsa": ["dsa"],
        "knapsack": ["dsa"],
        "graph algorithm": ["dsa"],
        "time complexity": ["dsa"],
        "ml pipeline": ["ai_ml"],
        "overfitting": ["ai_ml"],
        "regularization": ["ai_ml"],
        "training loop": ["ai_ml"],
        "ai/ml": ["ai_ml"],
    }

    def __init__(
        self,
        *,
        registry: SkillRegistry,
        config: SkillConfig | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._registry = registry
        self._config = config or SkillConfig()
        self._logger = logger or _LOG

    async def route(
        self,
        context: SkillContext,
        query: str = "",
    ) -> list[SkillPort]:
        """Select the best Skill Packs for the given context.

        Returns skills sorted by relevance (highest first).
        """
        if not self._config.enable_auto_routing:
            return self._registry.get_prioritized()

        candidates: dict[str, float] = {}

        # Route by query text matching if provided
        if query:
            q_lower = query.lower()
            for key in sorted(self.QUERY_ROUTES.keys(), key=len, reverse=True):
                pattern = r'(?:^|[\s,.;:!?()\/\\-])' + re.escape(key) + r'(?:$|[\s,.;:!?()\/\\-])'
                if re.search(pattern, q_lower):
                    for s_name in self.QUERY_ROUTES[key]:
                        score = 1.0 + (len(key) / 100.0)
                        candidates[s_name] = max(candidates.get(s_name, 0), score)

        # Route by project type
        project_type = context.project.project_type.lower()
        project_routes = {
            "python": "python",
            "react": "react",
            "next": "nextjs",
            "node": "nodejs",
            "java": "java",
            "c": "c",
            "cpp": "cpp",
            "docker": "docker",
            "kubernetes": "kubernetes",
            "mixed": None,
        }
        route_name = project_routes.get(project_type)
        if route_name:
            candidates[route_name] = max(candidates.get(route_name, 0), 0.9)

        # Route by file extension
        current_file = context.current_file
        if current_file and current_file.extension:
            ext = current_file.extension.lower()
            if not ext.startswith("."):
                ext = f".{ext}"
            ext_routes = self.EXTENSION_ROUTES.get(ext, [])
            for r in ext_routes:
                candidates[r] = max(candidates.get(r, 0), 0.9)

        # Route by filename match
        if current_file:
            fname = Path(current_file.path).name
            for pattern, skill_names in self.FILENAME_ROUTES.items():
                if pattern.startswith("*."):
                    if fname.endswith(pattern[1:]):
                        for s in skill_names:
                            candidates[s] = max(candidates.get(s, 0), 0.95)
                elif pattern.endswith("/*.yaml"):
                    if fname.endswith(".yaml") and "k8s" in Path(current_file.path).parts:
                        for s in skill_names:
                            candidates[s] = max(candidates.get(s, 0), 0.95)
                elif fname == pattern:
                    for s in skill_names:
                        candidates[s] = max(candidates.get(s, 0), 1.0)

        # Route by frameworks
        for framework in context.project.frameworks:
            fw_routes = {
                "django": "django",
                "fastapi": "fastapi",
                "express": "express",
                "react": "react",
                "nextjs": "nextjs",
                "spring": "java",
            }
            skill_name = fw_routes.get(framework.lower())
            if skill_name:
                candidates[skill_name] = max(candidates.get(skill_name, 0), 0.85)

        # Route by languages
        for language in context.project.languages:
            lang_routes = {
                "python": "python",
                "javascript": "javascript",
                "typescript": "typescript",
                "java": "java",
                "c": "c",
                "cpp": "cpp",
                "sql": "sql",
            }
            skill_name = lang_routes.get(language.lower())
            if skill_name:
                candidates[skill_name] = max(candidates.get(skill_name, 0), 0.8)

        # Add general-purpose skills for mixed projects
        if project_type == "mixed" or context.project.is_monorepo:
            candidates["docker"] = max(candidates.get("docker", 0), 0.5)
            candidates["git"] = max(candidates.get("git", 0), 0.5)
            candidates["devops"] = max(candidates.get("devops", 0), 0.4)

        # Resolve candidate names to actual SkillPort instances
        result: list[SkillPort] = []
        seen: set[str] = set()
        sorted_candidates = sorted(
            candidates.items(),
            key=lambda x: (-x[1], x[0]),
        )

        for name, _ in sorted_candidates:
            skill = self._registry.get(name)
            if skill and name not in seen:
                result.append(skill)
                seen.add(name)

        # If routing found nothing, use prioritized fallback
        if not result and self._config.routing_fallback_to_general:
            result = self._registry.get_prioritized()

        limit = self._config.routing_max_results
        return result[:limit]

    async def route_by_file(
        self,
        file_path: str,
        project: ProjectContext,
    ) -> list[SkillPort]:
        """Convenience: route by a single file path."""
        ext = Path(file_path).suffix.lower()
        fname = Path(file_path).name
        context = SkillContext(
            project=project,
            current_file=type('obj', (object,), {
                'path': file_path,
                'extension': ext,
                'name': fname,
            })(),
        )
        return await self.route(context)
