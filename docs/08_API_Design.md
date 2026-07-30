# 08. API & Protocol Specifications

This document details the interface contracts, WebSocket protocols, and push notification schemas for the Naira-OS system.

---

## 1. Overview & Protocol Architecture

Naira-OS provides dual-gateway interfaces for presentation layer clients:
- **Local Gateway (`/ws/naira`):** Bi-directional WebSocket endpoint operating on local HTTP/WS for desktop shell interfaces, Web UIs, and local IPC.
- **Remote Bridge Gateway (`/ws/remote`):** Publicly routable, cryptographically authenticated WebSocket endpoint operating over an Ngrok tunnel for remote Android device synchronization and mobile control.

---

## 2. Remote Bridge WebSocket Protocol (`/ws/remote`)

Located at [`remote_router.py`](file:///c:/Users/user/Desktop/Project-AIF-main/backend/modules/remote_bridge/remote_router.py).

### A. Connection Endpoint
* **URI:** `wss://<ngrok-domain>/ws/remote`
* **Default Tunnel Target:** `wss://swampland-flatten-rockstar.ngrok-free.dev/ws/remote`
* **Transport:** Secure WebSockets (WSS)

### B. Authentication Handshake Sequence

Upon connecting to `/ws/remote`, the client MUST immediately send a cryptographically signed JSON handshake payload as its first frame.

#### Handshake Request Frame
```json
{
  "action": "AUTH_HANDSHAKE",
  "client_id": "android_remote_vault_01",
  "timestamp": "2026-07-30T12:00:00.000000+00:00",
  "nonce": "4f8a19e2b3c4d5e6f7a8b9c0d1e2f3a4",
  "signature": "7d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b7c6d5e4f3a2b1c0d9e"
}
```

#### Signature Calculation Rule
The signature is an HMAC-SHA256 digest computed using the `REMOTE_BRIDGE_MASTER_KEY`:
$$\text{Signing Base} = \text{timestamp} + ":" + \text{nonce} + ":" + \text{canonical\_json}(\text{payload\_excluding\_signature\_timestamp\_nonce})$$

#### Handshake Success Response
```json
{
  "status": "authenticated",
  "message": "Handshake successful"
}
```

#### Handshake Error Responses
- **Invalid Payload Format:** Connection closed with WebSocket status code `4000` ("Invalid handshake format").
- **Signature / Replay Verification Failed:** Server sends error response and closes connection with WebSocket status code `4001` ("Authentication failed"):
```json
{
  "status": "error",
  "message": "Authentication failed"
}
```

### C. Offline Action Queue Auto-Flush
Immediately after a client completes successful authentication, the server flushes all actions pending in the `OfflineActionQueue` directly over the WebSocket before listening for new incoming frames.

### D. Interactive Message Exchange

#### Incoming Client Action Frame Format
```json
{
  "action": "TOGGLE_WIFI",
  "payload": {
    "enabled": true
  },
  "timestamp": "2026-07-30T12:01:00.000000+00:00",
  "nonce": "b1c2d3e4f5a678901234567890abcdef",
  "signature": "3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b"
}
```

#### Server Acknowledgment Frame Format
```json
{
  "status": "received",
  "action": "TOGGLE_WIFI",
  "timestamp": "2026-07-30T12:01:00.000000+00:00"
}
```

---

## 3. Firebase Cloud Messaging (FCM) Push Payload Schema

Located at [`fcm_manager.py`](file:///c:/Users/user/Desktop/Project-AIF-main/backend/modules/remote_bridge/fcm_manager.py).

The `FCMDispatcher` triggers background device wake-ups by dispatching silent, data-only push notifications via Firebase Admin SDK.

### A. FCM Message Payload Structure

```json
{
  "message": {
    "token": "eXamPle_Fcm_RegIstRaTioN_TokEn_1234567890",
    "data": {
      "action": "WAKEUP",
      "tunnel_uri": "wss://swampland-flatten-rockstar.ngrok-free.dev/ws/remote"
    },
    "android": {
      "priority": "high",
      "ttl": "3600s"
    }
  }
}
```

### B. Field Specifications

| Field Name | Type | Description | Required |
|------------|------|-------------|----------|
| `token` | String | Target Android device's unique FCM registration token | Yes |
| `data.action` | String | Action identifier for client parsing (default: `"WAKEUP"`) | Yes |
| `data.tunnel_uri` | String | Target WebSocket Ngrok URI for immediate client connection | Yes |
| `android.priority` | String | Set to `"high"` to bypass Android Doze mode constraints | Yes |
| `android.ttl` | Integer/String | Time-To-Live in seconds (`3600` = 1 hour) | Yes |

### C. Client Handling Behavior
1. **Silent Processing:** The payload contains NO `notification` body, ensuring no status bar banner is rendered to the user.
2. **Background Wake-Up:** High-priority status forces the Android OS to grant CPU execution time to `FirebaseMessagingService`.
3. **Automatic Tunnel Connect:** Android background service extracts `tunnel_uri` and opens the WebSocket connection to `/ws/remote`.
