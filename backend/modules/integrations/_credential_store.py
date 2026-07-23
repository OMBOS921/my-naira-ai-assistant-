# IMPORTANT: data/credentials/ must be in .gitignore
"""
CredentialStore — secure local storage for OAuth tokens and API credentials.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

_LOG = logging.getLogger("naira.integrations.credential_store")


class CredentialStore:
    """Manages secure local storage of OAuth tokens and API credentials."""

    def __init__(
        self,
        base_dir: str = "data/credentials",
        logger: logging.Logger | None = None,
    ) -> None:
        self._logger = logger or _LOG
        self._base_path = Path(base_dir).resolve()
        try:
            self._base_path.mkdir(parents=True, exist_ok=True)
            if os.name != "nt":
                os.chmod(self._base_path, 0o700)
        except Exception as exc:
            self._logger.warning("Error creating credentials directory '%s': %s", self._base_path, exc)

    def _get_service_path(self, service: str) -> Path:
        return self._base_path / f"{service}.json"

    def save_token(self, service: str, token_data: dict[str, Any]) -> None:
        """Save credential token dictionary to disk as JSON."""
        file_path = self._get_service_path(service)
        try:
            temp_path = file_path.with_suffix(".tmp")
            temp_path.write_text(json.dumps(token_data, indent=2), encoding="utf-8")
            if os.name != "nt":
                try:
                    os.chmod(temp_path, 0o600)
                except Exception:
                    pass
            temp_path.replace(file_path)
            self._logger.debug("Saved credentials for service '%s'", service)
        except Exception as exc:
            self._logger.error("Failed to save credentials for service '%s': %s", service, exc)

    def load_token(self, service: str) -> dict[str, Any] | None:
        """Load credential token dictionary from disk. Returns None on error."""
        file_path = self._get_service_path(service)
        if not file_path.is_file():
            return None
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
            return None
        except Exception as exc:
            self._logger.warning("Failed to load credentials for service '%s': %s", service, exc)
            return None

    def delete_token(self, service: str) -> bool:
        """Delete stored credentials for a service. Returns True if deleted."""
        file_path = self._get_service_path(service)
        if file_path.is_file():
            try:
                file_path.unlink()
                self._logger.debug("Deleted credentials for service '%s'", service)
                return True
            except Exception as exc:
                self._logger.error("Failed to delete credentials for service '%s': %s", service, exc)
                return False
        return False

    def has_token(self, service: str) -> bool:
        """Check whether credential file exists for a service."""
        return self._get_service_path(service).is_file()

    def list_connected_services(self) -> list[str]:
        """Scan base_dir for JSON credential files and return service names."""
        if not self._base_path.is_dir():
            return []
        services: list[str] = []
        for file in self._base_path.glob("*.json"):
            if file.is_file() and not file.name.startswith("."):
                services.append(file.stem)
        return sorted(services)
