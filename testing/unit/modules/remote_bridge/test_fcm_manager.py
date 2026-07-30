"""Unit tests for FCM Wake-Up & Ngrok Tunnel Configuration Manager (backend/modules/remote_bridge/fcm_manager.py)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.modules.remote_bridge.fcm_manager import (
    FCMDispatcher,
    RemoteBridgeConfig,
)


class TestRemoteBridgeConfig:
    def test_default_config(self) -> None:
        config = RemoteBridgeConfig()
        assert "ws" in config.ngrok_tunnel_uri
        assert config.websocket_target_uri == config.ngrok_tunnel_uri
        assert config.credentials_path.name == "firebase_credentials.json"


    def test_custom_config(self, tmp_path: Path) -> None:
        custom_cred = tmp_path / "custom_cred.json"
        config = RemoteBridgeConfig(
            ngrok_tunnel_uri="wss://custom.ngrok-free.app/ws/remote",
            credentials_path=custom_cred,
        )
        assert config.ngrok_tunnel_uri == "wss://custom.ngrok-free.app/ws/remote"
        assert config.websocket_target_uri == "wss://custom.ngrok-free.app/ws/remote"
        assert config.credentials_path == custom_cred


class TestFCMDispatcher:
    @pytest.fixture
    def dispatcher(self, tmp_path: Path) -> FCMDispatcher:
        dummy_cred = tmp_path / "firebase_credentials.json"
        dummy_cred.write_text('{"type": "service_account"}', encoding="utf-8")
        config = RemoteBridgeConfig(credentials_path=dummy_cred)
        return FCMDispatcher(config=config)

    def test_initialize_firebase_missing_credentials(self, tmp_path: Path) -> None:
        missing_cred = tmp_path / "non_existent.json"
        dispatcher = FCMDispatcher(config=RemoteBridgeConfig(credentials_path=missing_cred))
        
        with patch("backend.modules.remote_bridge.fcm_manager.HAS_FIREBASE", True), \
             patch("backend.modules.remote_bridge.fcm_manager.firebase_admin") as mock_fb:
            mock_fb.get_app.side_effect = ValueError("No app")
            result = dispatcher.initialize_firebase()
            assert result is False

    def test_initialize_firebase_success(self, dispatcher: FCMDispatcher) -> None:
        with patch("backend.modules.remote_bridge.fcm_manager.HAS_FIREBASE", True), \
             patch("backend.modules.remote_bridge.fcm_manager.firebase_admin") as mock_fb, \
             patch("backend.modules.remote_bridge.fcm_manager.credentials") as mock_cred:
            mock_fb.get_app.side_effect = ValueError("No app")
            mock_fb.initialize_app.return_value = MagicMock()
            
            result = dispatcher.initialize_firebase()
            assert result is True
            mock_cred.Certificate.assert_called_once_with(str(dispatcher.config.credentials_path))
            mock_fb.initialize_app.assert_called_once()

    def test_initialize_firebase_already_initialized(self, dispatcher: FCMDispatcher) -> None:
        mock_app = MagicMock()
        with patch("backend.modules.remote_bridge.fcm_manager.HAS_FIREBASE", True), \
             patch("backend.modules.remote_bridge.fcm_manager.firebase_admin") as mock_fb:
            mock_fb.get_app.return_value = mock_app
            
            result = dispatcher.initialize_firebase()
            assert result is True
            assert dispatcher._app == mock_app

    @pytest.mark.asyncio
    async def test_send_wakeup_ping_invalid_token(self, dispatcher: FCMDispatcher) -> None:
        result = await dispatcher.send_wakeup_ping(device_token="")
        assert result["success"] is False
        assert "Invalid or missing device token" in result["error"]

    @pytest.mark.asyncio
    async def test_send_wakeup_ping_success(self, dispatcher: FCMDispatcher) -> None:
        with patch("backend.modules.remote_bridge.fcm_manager.HAS_FIREBASE", True), \
             patch("backend.modules.remote_bridge.fcm_manager.messaging") as mock_messaging, \
             patch.object(dispatcher, "initialize_firebase", return_value=True):
            
            dispatcher._app = MagicMock()
            mock_messaging.send.return_value = "projects/test/messages/msg_12345"
            
            res = await dispatcher.send_wakeup_ping(
                device_token="test_fcm_token_123",
                action_type="WAKEUP_WS",
                extra_data={"session_id": "sess_99"},
            )

            assert res["success"] is True
            assert res["message_id"] == "projects/test/messages/msg_12345"
            assert res["tunnel_uri"] == dispatcher.config.websocket_target_uri
            
            mock_messaging.Message.assert_called_once()
            _, kwargs = mock_messaging.Message.call_args
            assert kwargs["token"] == "test_fcm_token_123"
            assert kwargs["data"]["action"] == "WAKEUP_WS"
            assert kwargs["data"]["tunnel_uri"] == dispatcher.config.websocket_target_uri
            assert kwargs["data"]["session_id"] == "sess_99"

    @pytest.mark.asyncio
    async def test_send_wakeup_ping_firebase_error(self, dispatcher: FCMDispatcher) -> None:
        with patch("backend.modules.remote_bridge.fcm_manager.HAS_FIREBASE", True), \
             patch("backend.modules.remote_bridge.fcm_manager.messaging") as mock_messaging, \
             patch.object(dispatcher, "initialize_firebase", return_value=True):
            
            dispatcher._app = MagicMock()
            mock_messaging.send.side_effect = RuntimeError("FCM Service Unavailable")
            
            res = await dispatcher.send_wakeup_ping(device_token="test_token")
            assert res["success"] is False
            assert "FCM Service Unavailable" in res["error"]
