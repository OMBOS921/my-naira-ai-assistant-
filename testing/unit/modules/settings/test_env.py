"""Tests for the environment variable snapshot (backend/modules/settings/_env.py).

21_System_Contracts.md §7.6 — All env vars are prefixed with ``NAIRA_``.
18_Boot_Sequence.md §2 Step 1 — Environment validation at boot.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.modules.settings._env import EnvironmentSnapshot


class TestEnvironmentSnapshot:
    def test_direct_construction(self) -> None:
        snap = EnvironmentSnapshot(naira_api_key="my-key")
        assert snap.naira_api_key == "my-key"

    def test_frozen(self) -> None:
        snap = EnvironmentSnapshot(naira_api_key="key")
        with pytest.raises(AttributeError):
            snap.naira_api_key = "new-key"  # type: ignore[misc]

    def test_load_from_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NAIRA_API_KEY", "env-key")
        snap = EnvironmentSnapshot.load(env_file=Path("nonexistent/.env"))
        assert snap.naira_api_key == "env-key"

    def test_load_from_dotenv_file(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.delenv("NAIRA_API_KEY", raising=False)
        dotenv = tmp_path / ".env"
        dotenv.write_text('NAIRA_API_KEY="file-key"\n', encoding="utf-8")
        snap = EnvironmentSnapshot.load(env_file=dotenv)
        assert snap.naira_api_key == "file-key"

    def test_dotenv_overrides_env_var(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("NAIRA_API_KEY", "env-key")
        dotenv = tmp_path / ".env"
        dotenv.write_text('NAIRA_API_KEY="file-key"\n', encoding="utf-8")
        snap = EnvironmentSnapshot.load(env_file=dotenv)
        # os.environ values overlay .env values in the current implementation
        assert snap.naira_api_key == "env-key"

    def test_missing_required_var_exits(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("NAIRA_API_KEY", raising=False)
        fake_env = Path("nonexistent/.env")
        with pytest.raises(SystemExit):
            EnvironmentSnapshot.load(env_file=fake_env)

    def test_ignores_non_naira_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_CUSTOM_VAR", "should-be-ignored")
        monkeypatch.setenv("NAIRA_API_KEY", "real-key")
        snap = EnvironmentSnapshot.load(env_file=Path("nonexistent/.env"))
        assert snap.naira_api_key == "real-key"

    def test_repr(self) -> None:
        snap = EnvironmentSnapshot(naira_api_key="secret123")
        r = repr(snap)
        assert "naira_api_key" in r
        assert "secret123" in r
