"""Persistent, local-only configuration for the selected LLM provider."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

ProviderName = Literal["gemini", "deepseek"]


@dataclass(frozen=True)
class LLMProviderConfig:
    """The runtime configuration stored in the local user vault."""

    provider: ProviderName
    model: str
    api_key: str


class LLMConfigStore:
    """Read and atomically write the local LLM vault.

    The vault deliberately never exposes an API key through its public status
    methods.  It is a local desktop configuration file, not a shared secret
    store; restrictive file permissions are applied where supported.
    """

    def __init__(self, vault_path: Path | None = None) -> None:
        root_dir = Path(__file__).resolve().parents[3]
        self._vault_path = vault_path or root_dir / "memory" / "user_vault.json"

    @property
    def vault_path(self) -> Path:
        return self._vault_path

    def save(self, *, provider: ProviderName, model: str, api_key: str) -> LLMProviderConfig:
        if provider not in {"gemini", "deepseek"}:
            raise ValueError("Unsupported LLM provider")
        if not model.strip() or not api_key.strip():
            raise ValueError("Model and API key are required")

        config = LLMProviderConfig(provider=provider, model=model.strip(), api_key=api_key.strip())
        self._vault_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".user_vault-", suffix=".tmp", dir=self._vault_path.parent
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as vault_file:
                json.dump(asdict(config), vault_file, indent=2)
                vault_file.write("\n")
            os.replace(temporary_name, self._vault_path)
            self._restrict_permissions()
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
        return config

    def is_configured(self) -> bool:
        return self.get_active_config() is not None

    def get_active_config(self) -> LLMProviderConfig | None:
        try:
            payload = json.loads(self._vault_path.read_text(encoding="utf-8"))
            provider = payload.get("provider")
            model = payload.get("model")
            api_key = payload.get("api_key")
            if provider not in {"gemini", "deepseek"}:
                return None
            if not isinstance(model, str) or not model.strip():
                return None
            if not isinstance(api_key, str) or not api_key.strip():
                return None
            return LLMProviderConfig(provider=provider, model=model, api_key=api_key)
        except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError):
            return None

    def _restrict_permissions(self) -> None:
        try:
            os.chmod(self._vault_path, 0o600)
        except OSError:
            # Windows ACL management is environment-specific; atomic write still
            # prevents readers from observing a partial JSON document.
            pass
