"""
Environment variable loading and validation.

18_Boot_Sequence.md §2 Step 1.
21_System_Contracts.md §7.6.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

_ROOT_DIR: Final[Path] = Path(__file__).resolve().parent.parent.parent.parent
_ENV_FILE: Final[Path] = _ROOT_DIR / ".env"
_ENV_PREFIX: Final[str] = "GEMINI_"
_REQUIRED_ENV_VARS: Final[set[str]] = {"GEMINI_API_KEY"}


@dataclass(frozen=True)
class EnvironmentSnapshot:
    """Environment variables available to the application.

    Created during boot Step 1.  Modules receive this via constructor
    injection and must never access ``os.environ`` directly.

    21_System_Contracts.md §7.6.
    """

    naira_api_key: str = ""
    gemini_api_key: str = ""
    elevenlabs_api_key: str = ""
    porcupine_access_key: str = ""

    def __post_init__(self) -> None:
        key = self.naira_api_key or self.gemini_api_key
        object.__setattr__(self, "naira_api_key", key)
        object.__setattr__(self, "gemini_api_key", key)

    @classmethod
    def load(cls, env_file: Path | None = None) -> EnvironmentSnapshot:
        """Load and validate environment variables.

        Reads ``.env`` then overlays OS environment.  An empty snapshot is a
        supported first-run state: the local API vault supplies the LLM key
        after the backend starts.
        """
        env: dict[str, str] = {}

        env_path = env_file or _ENV_FILE
        if env_path.is_file():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip().strip("\"'")

        for key, value in os.environ.items():
            if key.startswith("NAIRA_") or key.startswith("GEMINI_"):
                env[key] = value

        api_key = (
            env.get("NAIRA_API_KEY")
            or env.get("GEMINI_API_KEY")
            or env.get("NAIRA_GEMINI_API_KEY")
            or ""
        )

        return cls(
            naira_api_key=api_key,
            gemini_api_key=api_key,
            elevenlabs_api_key=env.get("NAIRA_ELEVENLABS_API_KEY", ""),
            porcupine_access_key=env.get("NAIRA_PORCUPINE_ACCESS_KEY", ""),
        )
