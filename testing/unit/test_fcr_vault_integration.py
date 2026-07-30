"""Unit test for FastCommandRouter dynamic Groq API Key retrieval from SettingsManager & Vault."""

import logging
import pytest
from unittest.mock import MagicMock

from backend.modules.settings.settings_module import SettingsManager
from backend.runtime.fast_command_router import FastCommandRouter


@pytest.mark.asyncio
async def test_fcr_fetches_groq_key_from_settings(caplog):
    """Test that FastCommandRouter retrieves Groq API Key from SettingsManager when available."""
    caplog.set_level(logging.INFO)

    mock_settings = MagicMock(spec=SettingsManager)
    mock_settings.get.side_effect = lambda key, default=None: "gsk_vault_test_key_12345" if key in ("api_keys.groq", "groq_api_key") else default
    mock_settings.get_api_key.return_value = "gsk_vault_test_key_12345"

    router = FastCommandRouter(settings_manager=mock_settings)

    assert router._api_key == "gsk_vault_test_key_12345"


@pytest.mark.asyncio
async def test_fcr_graceful_handling_missing_groq_key(caplog):
    """Test that FastCommandRouter logs warning and degrades gracefully when Groq API Key is missing."""
    caplog.set_level(logging.WARNING)

    mock_settings = MagicMock(spec=SettingsManager)
    mock_settings.get.return_value = ""
    mock_settings.get_api_key.return_value = ""

    router = FastCommandRouter(api_key="", settings_manager=mock_settings)

    assert router._api_key == ""
    assert any("Groq API key missing in Vault" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_settings_manager_get_dot_notation():
    """Test SettingsManager dot-notation accessor get() and get_api_key()."""
    sm = SettingsManager()
    sm._raw_config = {
        "api_keys": {
            "groq": "gsk_raw_test_9999"
        }
    }

    assert sm.get("api_keys.groq") == "gsk_raw_test_9999"
    assert sm.get_api_key("groq") == "gsk_raw_test_9999"
    assert sm.get("nonexistent.key", "default_val") == "default_val"
