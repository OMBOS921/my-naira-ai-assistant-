"""FCM Wake-Up & Ngrok Tunnel Configuration Manager.

Handles loading Firebase credentials securely, configuring the Ngrok remote tunnel URI,
and dispatching high-priority data-only FCM messages to wake up remote devices from Doze mode.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

try:
    import firebase_admin
    from firebase_admin import credentials, messaging
    HAS_FIREBASE = True
except ImportError:
    firebase_admin = None
    credentials = None
    messaging = None
    HAS_FIREBASE = False

logger = logging.getLogger(__name__)

DEFAULT_CREDENTIALS_PATH = Path(__file__).resolve().parent.parent.parent.parent / "firebase_credentials.json"
DEFAULT_NGROK_DOMAIN = "wss://swampland-flatten-rockstar.ngrok-free.dev/ws/remote"


@dataclass(frozen=True)
class RemoteBridgeConfig:
    """Configuration settings for Remote Bridge connectivity."""

    ngrok_tunnel_uri: str = DEFAULT_NGROK_DOMAIN
    credentials_path: Path = DEFAULT_CREDENTIALS_PATH

    @property
    def websocket_target_uri(self) -> str:
        """Return formatted WebSocket endpoint URI."""
        return self.ngrok_tunnel_uri


class FCMDispatcher:
    """Dispatches FCM wake-up pings to registered Android devices."""

    def __init__(self, config: Optional[RemoteBridgeConfig] = None) -> None:
        self.config = config or RemoteBridgeConfig()
        self._app: Optional[Any] = None

    def initialize_firebase(self) -> bool:
        """Initialize Firebase Admin SDK if not already initialized."""
        if not HAS_FIREBASE:
            logger.error("firebase-admin package is not installed.")
            return False

        try:
            # Avoid re-initializing if default app already exists
            try:
                self._app = firebase_admin.get_app()
                return True
            except ValueError:
                pass

            cred_path = Path(self.config.credentials_path)
            if not cred_path.is_file():
                logger.error("Firebase credentials file not found at %s", cred_path)
                return False

            cred = credentials.Certificate(str(cred_path))
            self._app = firebase_admin.initialize_app(cred)
            logger.info("Firebase Admin initialized successfully.")
            return True
        except Exception as exc:
            logger.exception("Failed to initialize Firebase Admin SDK: %s", exc)
            return False

    async def send_wakeup_ping(
        self,
        device_token: str,
        action_type: str = "WAKEUP",
        extra_data: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """Send a silent, data-only FCM push notification to wake up target device.

        Args:
            device_token: FCM Registration token of the target Android client.
            action_type: Action type identifier for the client app parser.
            extra_data: Optional additional dictionary key-values to pass in FCM data.

        Returns:
            Dict containing status, message_id (on success), or error message (on failure).
        """
        if not device_token or not isinstance(device_token, str):
            return {"success": False, "error": "Invalid or missing device token"}

        if not self._app:
            initialized = self.initialize_firebase()
            if not initialized:
                return {"success": False, "error": "Firebase Admin SDK initialization failed"}

        payload_data = {
            "action": action_type,
            "tunnel_uri": self.config.websocket_target_uri,
        }
        if extra_data:
            payload_data.update(extra_data)

        # High priority Android config for silent background wake-up from Doze mode
        android_config = messaging.AndroidConfig(
            priority="high",
            ttl=3600,
        )

        message = messaging.Message(
            data=payload_data,
            token=device_token,
            android=android_config,
        )

        try:
            # Run blocking firebase send call in async threadpool pool loop
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, messaging.send, message)
            logger.info("FCM wakeup ping sent successfully. Message ID: %s", response)
            return {
                "success": True,
                "message_id": response,
                "tunnel_uri": self.config.websocket_target_uri,
            }
        except Exception as exc:
            logger.exception("Error sending FCM wakeup ping: %s", exc)
            return {"success": False, "error": str(exc)}
