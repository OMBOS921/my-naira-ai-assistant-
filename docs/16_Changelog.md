# 16. System Changelog

All notable changes, architectural updates, and phase releases for the Naira-OS project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased] / [Phase 4.2 Blueprint] - 2026-07-30

### Planned
- Native Android Remote App & Security Vault frontend.
- Out-of-band QR code device pairing.
- Hardware-backed private key storage (`AndroidKeyStore`).
- Android NDK native C++ cryptographic verification layer.
- Step-up biometric challenge UI for high-risk action confirmation (`score > 80`).

---

## [Phase 4.1] - Remote Bridge Backend & Cryptographic Gateway - 2026-07-30

### Added
- **FCM Wake-Up Dispatcher (`FCMDispatcher`):**
  - Created [`fcm_manager.py`](file:///c:/Users/user/Desktop/Project-AIF-main/backend/modules/remote_bridge/fcm_manager.py) to manage Firebase Admin SDK initialization and send high-priority silent background FCM wake-up pings.
  - Implemented `RemoteBridgeConfig` to manage default Ngrok tunnel URI (`wss://swampland-flatten-rockstar.ngrok-free.dev/ws/remote`) and Firebase credentials path (`firebase_credentials.json`).
  - Implemented background thread-pool dispatching (`run_in_executor`) to prevent event-loop blocking.
- **Ngrok WebSocket Router (`remote_router.py`):**
  - Created [`remote_router.py`](file:///c:/Users/user/Desktop/Project-AIF-main/backend/modules/remote_bridge/remote_router.py) exposing `@router.websocket("/ws/remote")` endpoint over public Ngrok tunnel.
  - Implemented `RemoteBridgeManager` to track active WebSocket connection state and manage action routing.
  - Implemented initial handshake authentication sequence verifying cryptographic signatures, nonces, and timestamps before accepting incoming connections.
- **Offline Action Queue (`OfflineActionQueue`):**
  - Created thread-safe async in-memory queue to store signed command payloads when target mobile devices are offline.
  - Implemented automatic queue flushing immediately upon client authentication upon re-connection.
- **Zero-Trust Security Engine (`bridge_security.py`):**
  - Created [`bridge_security.py`](file:///c:/Users/user/Desktop/Project-AIF-main/backend/modules/remote_bridge/bridge_security.py) providing `SecurityRegistrar` for HMAC-SHA256 signature generation and payload canonicalization (`timestamp:nonce:canonical_json`).
  - Implemented timestamp freshness validation with a 5-minute replay window (`MAX_TIMESTAMP_AGE_SECONDS = 300`).
  - Implemented 16-byte random hex `nonce` generation and validation for anti-replay protection.
  - Implemented `RiskEngine` with dynamic risk scoring (0–100 scale) assigning action impact scores and flagging `requires_biometric = True` when `risk_score > 80` (e.g., `OPEN_BANK_APP`, `TRANSFER_FUNDS`, `CHANGE_PASSWORD`, `FACTORY_RESET`).
- **Comprehensive Unit Testing Suite:**
  - Added unit test suites for `fcm_manager`, `remote_router`, and `bridge_security` verifying initial connection handshakes, auth failures, offline queue flushes, signature verifications, and risk evaluations.

---

## [Phase 4.0] - Proactive Watchdog & LLM Response Caching

### Added
- `ProactiveWatchdog` background health engine with warm-up CPU sampling and voice synthesis alerts.
- In-memory `LLMResponseCache` with strict tool-call bypassing.
- Dynamic provider fallback (Gemini → Ollama → DeepSeek).

---

## [Phase 3.0] - Interactive CLI & WebSocket Gateway

### Added
- Real-time FastAPI `/ws/naira` endpoint with `system_init` identity sync and barge-in audio interrupt support.
- Standalone CLI runner [`run_cli.py`](file:///c:/Users/user/Desktop/Project-AIF-main/run_cli.py).

---

## [Phase 2.0] - Master Fast Command Router (FCR Phase 2)

### Added
- Deterministic FCR matching engine with sub-5ms latency and length-weighted candidate scoring.
- Memory SQLite client manager.

---

## [Phase 1.0] - Core Foundation & System Bootstrap

### Added
- Core Orchestrator FSM and dependency injection container (`DIContainer`).
- Non-blocking daily rotating file Logger and `.env` configuration manager.
