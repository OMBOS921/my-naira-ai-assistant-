# PC_SIDE_NOTE.md — Ngrok Tunnel Auto-Healing via FCM URL-Update Payload

## 1. Problem Statement & Architecture Gap
When the Naira-OS PC backend restarts or re-establishes an Ngrok tunnel session, Ngrok issues a **new dynamic tunnel URL** (e.g. `wss://abcd-1234.ngrok-free.app/ws/remote`).

Previously, the Android client app only received the tunnel URL during initial QR code pairing and saved it securely in `EncryptedSharedPreferences` via `CryptoVault`. Upon a PC reboot:
1. The old tunnel URL becomes dead (`404 / Connection Refused`).
2. The Android client will endlessly fail reconnect attempts against the stale URL.
3. Plain wake pings (`{"wake": true}`) fail to restore connectivity because the stored endpoint itself is invalid.

## 2. Dynamic Auto-Healing Protocol (`url_update`)

To bridge this operational gap without requiring manual re-pairing via QR code, the PC backend (`fcm_manager.py`) MUST dispatch a high-priority FCM data payload of type `url_update` whenever the Ngrok tunnel URI changes or restarts.

### 2.1 FCM Data Payload Schema
```json
{
  "type": "url_update",
  "new_url": "wss://<new-ngrok-subdomain>.ngrok-free.app/ws/remote",
  "hmac": "<HMAC-SHA256 hex signature>",
  "timestamp": "<UTC UNIX timestamp in seconds>"
}
```

### 2.2 Security Specifications (HMAC Signature & Anti-Replay)
To prevent unauthorized URL hijacking or replay attacks:
1. **Master Key**: Uses the exact same 256-bit Master Key shared between the PC backend and Android client during QR code pairing.
2. **Payload to Sign**: The plain string concatenation of `new_url` and `timestamp`:
   ```python
   payload_str = f"{new_url}{timestamp}"
   ```
3. **HMAC Calculation**: HMAC-SHA256 encoded as a lowercase hex string:
   ```python
   import hmac, hashlib, time

   timestamp = str(int(time.time()))
   payload = f"{new_url}{timestamp}"
   signature = hmac.new(
       master_key.encode("utf-8"),
       payload.encode("utf-8"),
       hashlib.sha256
   ).hexdigest()
   ```
4. **Android Client Verification Rules**:
   - **Timestamp Window**: Remote `timestamp` must be within **±45 seconds** of local Android system time.
   - **HMAC Verification**: Constant-time byte array comparison via `HmacVerifier.verifyHmac(payloadToVerify, hmac, masterKey)`.
   - **Rejection Logging**: If signature check or timestamp check fails, Android logs `URL_UPDATE_REJECTED` and ignores the payload completely.
   - **Persistence & Reconnection**: On success, calls `CryptoVault.updateTunnelUrl(newUrl)` and triggers `RemoteBridgeClient.reconnect(newUrl)`.

## 3. PC Backend Integration (`fcm_manager.py`)

Add the following method to `FCMDispatcher` inside `backend/modules/remote_bridge/fcm_manager.py`:

```python
async def send_url_update(
    self,
    device_token: str,
    new_url: str,
    master_key: str
) -> dict[str, Any]:
    """Dispatches a signed URL-Update payload to update Android remote tunnel target."""
    import time, hmac, hashlib

    timestamp = str(int(time.time()))
    payload_str = f"{new_url}{timestamp}"
    signature = hmac.new(
        master_key.encode("utf-8"),
        payload_str.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    fcm_data = {
        "type": "url_update",
        "new_url": new_url,
        "hmac": signature,
        "timestamp": timestamp
    }

    return await self.send_wakeup_ping(
        device_token=device_token,
        action_type="URL_UPDATE",
        extra_data=fcm_data
    )
```

Trigger `send_url_update()` automatically whenever Ngrok starts or auto-reconnects on the PC.
