"""Unit tests for Remote Bridge Ngrok WebSocket Router & Offline Action Queue."""

import asyncio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.modules.remote_bridge.bridge_security import SecurityRegistrar
from backend.modules.remote_bridge.remote_router import (
    OfflineActionQueue,
    RemoteBridgeManager,
    get_bridge_manager,
    router as remote_bridge_router,
)


@pytest.fixture
def test_app():
    """Create a test FastAPI app with remote bridge router included."""
    app = FastAPI()
    app.include_router(remote_bridge_router)
    return app


@pytest.fixture
def custom_manager():
    """Create a fresh isolated RemoteBridgeManager instance."""
    return RemoteBridgeManager(security_registrar=SecurityRegistrar(master_key="test-secret-key"))


@pytest.mark.asyncio
async def test_offline_action_queue_basic():
    """Test OfflineActionQueue operations: enqueue, flush, size, is_empty, clear."""
    registrar = SecurityRegistrar(master_key="test-secret")
    queue = OfflineActionQueue(security_registrar=registrar)

    assert await queue.is_empty() is True
    assert await queue.size() == 0

    action1 = {"action": "TOGGLE_WIFI", "state": "ON"}
    signed1 = await queue.enqueue(action1, auto_sign=True)

    assert "signature" in signed1
    assert "timestamp" in signed1
    assert "nonce" in signed1
    assert await queue.size() == 1
    assert await queue.is_empty() is False

    action2 = {"action": "GET_BATTERY"}
    await queue.enqueue(action2, auto_sign=True)
    assert await queue.size() == 2

    flushed = await queue.flush()
    assert len(flushed) == 2
    assert flushed[0]["action"] == "TOGGLE_WIFI"
    assert flushed[1]["action"] == "GET_BATTERY"
    assert await queue.size() == 0
    assert await queue.is_empty() is True


@pytest.mark.asyncio
async def test_offline_action_queue_clear():
    """Test clearing offline action queue."""
    queue = OfflineActionQueue()
    await queue.enqueue({"action": "LOCK_DEVICE"})
    assert await queue.size() == 1
    await queue.clear()
    assert await queue.size() == 0


def test_websocket_authentication_success(test_app):
    """Test successful WebSocket handshake authentication using TestClient."""
    manager = get_bridge_manager()
    registrar = manager.security_registrar
    auth_handshake = registrar.sign_command({"action": "AUTHENTICATE"})

    client = TestClient(test_app)
    with client.websocket_connect("/ws/remote") as websocket:
        websocket.send_json(auth_handshake)
        response = websocket.receive_json()
        assert response["status"] == "authenticated"
        assert response["message"] == "Handshake successful"


def test_websocket_authentication_failure_invalid_sig(test_app):
    """Test WebSocket handshake failure with invalid signature."""
    client = TestClient(test_app)
    invalid_handshake = {
        "action": "AUTHENTICATE",
        "timestamp": "2026-07-30T12:00:00+00:00",
        "nonce": "fake_nonce",
        "signature": "invalid_signature_hash",
    }
    with client.websocket_connect("/ws/remote") as websocket:
        websocket.send_json(invalid_handshake)
        response = websocket.receive_json()
        assert response["status"] == "error"
        assert response["message"] == "Authentication failed"


def test_websocket_authentication_failure_missing_fields(test_app):
    """Test WebSocket handshake failure with missing cryptographic signature fields."""
    client = TestClient(test_app)
    incomplete_handshake = {"action": "AUTHENTICATE"}
    with client.websocket_connect("/ws/remote") as websocket:
        websocket.send_json(incomplete_handshake)
        response = websocket.receive_json()
        assert response["status"] == "error"
        assert response["message"] == "Authentication failed"


@pytest.mark.asyncio
async def test_offline_queue_flushing_on_reconnect(test_app):
    """Test that pending offline actions flush automatically when client connects."""
    manager = get_bridge_manager()
    registrar = manager.security_registrar

    # Pre-enqueue pending actions while offline
    await manager.queue.enqueue({"action": "TOGGLE_WIFI"})
    await manager.queue.enqueue({"action": "TAKE_SCREENSHOT"})

    auth_handshake = registrar.sign_command({"action": "AUTHENTICATE"})

    client = TestClient(test_app)
    with client.websocket_connect("/ws/remote") as websocket:
        websocket.send_json(auth_handshake)
        auth_resp = websocket.receive_json()
        assert auth_resp["status"] == "authenticated"

        # Flushed action 1
        msg1 = websocket.receive_json()
        assert msg1["action"] == "TOGGLE_WIFI"

        # Flushed action 2
        msg2 = websocket.receive_json()
        assert msg2["action"] == "TAKE_SCREENSHOT"

    # Queue should be drained now
    assert await manager.queue.size() == 0


@pytest.mark.asyncio
async def test_send_action_online_vs_offline(custom_manager):
    """Test send_action behavior when device is offline vs online."""
    assert custom_manager.is_connected is False

    # Send action while offline -> queued
    sent_online = await custom_manager.send_action({"action": "SET_VOLUME", "level": 80})
    assert sent_online is False
    assert await custom_manager.queue.size() == 1

    flushed = await custom_manager.queue.flush()
    assert flushed[0]["action"] == "SET_VOLUME"
