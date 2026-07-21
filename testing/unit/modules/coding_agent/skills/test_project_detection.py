"""Tests for ProjectDetector."""

from __future__ import annotations

import pytest

from backend.modules.coding_agent.skills.detection._project import ProjectDetector


@pytest.mark.asyncio
class TestProjectDetector:
    async def test_detect_unknown_project(self, tmp_project_dir) -> None:
        detector = ProjectDetector()
        ctx = await detector.detect(str(tmp_project_dir))
        assert ctx.project_type == "unknown"

    async def test_detect_python_project(self, tmp_project_dir) -> None:
        (tmp_project_dir / "setup.py").touch()
        detector = ProjectDetector()
        ctx = await detector.detect(str(tmp_project_dir))
        assert ctx.project_type == "python"
        assert "python" in ctx.languages

    async def test_detect_python_with_requirements(self, tmp_project_dir) -> None:
        (tmp_project_dir / "requirements.txt").touch()
        detector = ProjectDetector()
        ctx = await detector.detect(str(tmp_project_dir))
        assert ctx.project_type == "python"

    async def test_detect_docker_project(self, tmp_project_dir) -> None:
        (tmp_project_dir / "Dockerfile").touch()
        detector = ProjectDetector()
        ctx = await detector.detect(str(tmp_project_dir))
        assert ctx.project_type == "docker"

    async def test_detect_node_project(self, tmp_project_dir) -> None:
        (tmp_project_dir / "package.json").write_text('{"name": "test"}')
        detector = ProjectDetector()
        ctx = await detector.detect(str(tmp_project_dir))
        assert ctx.project_type in ("node", "mixed")

    async def test_detect_java_project(self, tmp_project_dir) -> None:
        (tmp_project_dir / "pom.xml").write_text("<project></project>")
        detector = ProjectDetector()
        ctx = await detector.detect(str(tmp_project_dir))
        assert ctx.project_type == "java"
        assert ctx.build_system == "maven"

    async def test_detect_c_project(self, tmp_project_dir) -> None:
        (tmp_project_dir / "Makefile").touch()
        detector = ProjectDetector()
        ctx = await detector.detect(str(tmp_project_dir))
        assert ctx.project_type == "cpp"

    async def test_detect_cpp_project(self, tmp_project_dir) -> None:
        (tmp_project_dir / "CMakeLists.txt").touch()
        detector = ProjectDetector()
        ctx = await detector.detect(str(tmp_project_dir))
        assert ctx.project_type in ("cpp", "c")

    async def test_detect_monorepo(self, tmp_project_dir) -> None:
        (tmp_project_dir / "lerna.json").touch()
        detector = ProjectDetector()
        ctx = await detector.detect(str(tmp_project_dir))
        assert ctx.project_type == "monorepo"

    async def test_detect_kubernetes(self, tmp_project_dir) -> None:
        (tmp_project_dir / "k8s").mkdir()
        detector = ProjectDetector()
        ctx = await detector.detect(str(tmp_project_dir))
        assert ctx.project_type == "kubernetes"

    async def test_detect_mixed_project(self, tmp_project_dir) -> None:
        (tmp_project_dir / "setup.py").touch()
        (tmp_project_dir / "Dockerfile").touch()
        (tmp_project_dir / "package.json").write_text('{"name": "test"}')
        detector = ProjectDetector()
        ctx = await detector.detect(str(tmp_project_dir))
        assert ctx.project_type == "mixed"

    async def test_detect_nonexistent_path(self) -> None:
        detector = ProjectDetector()
        ctx = await detector.detect("/nonexistent/path")
        assert ctx.project_type == "unknown"

    async def test_detect_django_project(self, tmp_project_dir) -> None:
        (tmp_project_dir / "pyproject.toml").write_text('[project]\ndependencies = ["django"]')
        detector = ProjectDetector()
        ctx = await detector.detect(str(tmp_project_dir))
        assert ctx.project_type == "python"

    async def test_project_context_fields(self, tmp_project_dir) -> None:
        (tmp_project_dir / "setup.py").touch()
        detector = ProjectDetector()
        ctx = await detector.detect(str(tmp_project_dir))
        assert ctx.root_path != ""
        assert isinstance(ctx.file_count, int)
        assert isinstance(ctx.directory_count, int)
