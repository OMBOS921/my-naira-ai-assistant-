"""Tests for CapabilityDetector."""

from __future__ import annotations

import pytest

from backend.modules.coding_agent.skills.detection._capability import CapabilityDetector


@pytest.mark.asyncio
class TestCapabilityDetector:
    async def test_detect_empty_project(self, tmp_project_dir) -> None:
        detector = CapabilityDetector()
        caps = await detector.detect(str(tmp_project_dir))
        assert caps["languages"] == []
        assert caps["build_system"] == ""

    async def test_detect_python_language(self, tmp_project_dir) -> None:
        (tmp_project_dir / "main.py").write_text("print('hello')")
        detector = CapabilityDetector()
        caps = await detector.detect(str(tmp_project_dir))
        assert "python" in caps["languages"]

    async def test_detect_javascript_language(self, tmp_project_dir) -> None:
        (tmp_project_dir / "app.js").touch()
        detector = CapabilityDetector()
        caps = await detector.detect(str(tmp_project_dir))
        assert "javascript" in caps["languages"]

    async def test_detect_java_language(self, tmp_project_dir) -> None:
        (tmp_project_dir / "Main.java").touch()
        detector = CapabilityDetector()
        caps = await detector.detect(str(tmp_project_dir))
        assert "java" in caps["languages"]

    async def test_detect_pytest(self, tmp_project_dir) -> None:
        (tmp_project_dir / "conftest.py").touch()
        detector = CapabilityDetector()
        caps = await detector.detect(str(tmp_project_dir))
        assert caps["test_framework"] == "pytest"

    async def test_detect_github_actions(self, tmp_project_dir) -> None:
        (tmp_project_dir / ".github").mkdir()
        (tmp_project_dir / ".github" / "workflows").mkdir()
        (tmp_project_dir / ".github" / "workflows" / "ci.yml").touch()
        detector = CapabilityDetector()
        caps = await detector.detect(str(tmp_project_dir))
        assert caps["ci_provider"] == "github_actions"

    async def test_detect_multiple_languages(self, tmp_project_dir) -> None:
        (tmp_project_dir / "main.py").touch()
        (tmp_project_dir / "app.js").touch()
        (tmp_project_dir / "styles.css").touch()
        detector = CapabilityDetector()
        caps = await detector.detect(str(tmp_project_dir))
        assert "python" in caps["languages"]
        assert "javascript" in caps["languages"]
        assert "css" in caps["languages"]

    async def test_detect_frameworks_from_package_json(self, tmp_project_dir) -> None:
        (tmp_project_dir / "package.json").write_text(
            '{"dependencies": {"react": "^18.0.0", "next": "^14.0.0"}}'
        )
        detector = CapabilityDetector()
        caps = await detector.detect(str(tmp_project_dir))
        assert "react" in caps["frameworks"]
        assert "nextjs" in caps["frameworks"]

    async def test_detect_build_system_from_cmake(self, tmp_project_dir) -> None:
        (tmp_project_dir / "CMakeLists.txt").touch()
        detector = CapabilityDetector()
        caps = await detector.detect(str(tmp_project_dir))
        assert caps["build_system"] == "cmake"

    async def test_detect_package_manager(self, tmp_project_dir) -> None:
        (tmp_project_dir / "yarn.lock").touch()
        detector = CapabilityDetector()
        caps = await detector.detect(str(tmp_project_dir))
        assert caps["package_manager"] == "yarn"

    async def test_detect_nonexistent_path(self) -> None:
        detector = CapabilityDetector()
        caps = await detector.detect("/nonexistent")
        assert caps == {}

    async def test_detect_with_file_list(self, tmp_project_dir) -> None:
        (tmp_project_dir / "main.py").touch()
        detector = CapabilityDetector()
        caps = await detector.detect(
            str(tmp_project_dir),
            project_files=["main.py"],
        )
        assert "python" in caps["languages"]
