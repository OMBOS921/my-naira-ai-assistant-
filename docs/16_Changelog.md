# 16. System Changelog

All notable changes, architectural updates, and phase releases for the Naira-OS project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Phase 4.2] - Browser Module Hardening & Capability Expansion - 2026-08-02

### Added
- **Exposed Existing & New Browser Tools (Phase 1 & Phase 2):**
  - Navigation & History: `browser_screenshot`, `browser_back`, `browser_forward`, `browser_reload`, `browser_new_tab`, `browser_close_tab`, `browser_list_tabs`, `browser_switch_tab`.
  - Element Waiting & Actionability: `browser_wait_for_selector` (`state="visible"` internal pre-wait for `click` and `fill`).
  - Richer Element Interactions: `browser_select_option`, `browser_hover`, `browser_right_click`, `browser_drag_and_drop`, `browser_check`, `browser_uncheck`, `browser_upload_file`, `browser_press_key`.
  - Cookies & Web Storage: `browser_get_cookies`, `browser_set_cookies`, `browser_clear_cookies`, `browser_get_local_storage`, `browser_set_local_storage`, `browser_clear_local_storage`, `browser_get_session_storage`, `browser_set_session_storage`, `browser_clear_session_storage`.
  - File Operations & PDF Export: `browser_export_pdf` (headless Chromium), `browser_download_file` with sandboxed storage (`BrowserDownloader` and `PathValidator`).
  - Code Execution: `browser_execute_js` with security policy gating.
- **Engine & Profile Support:**
  - Multi-engine support (`chromium`, `firefox`, `webkit`).
  - Persistent browser profiles via `user_data_dir`.
  - Custom HTTP headers and basic authentication support in `navigate()`.
- **Search Reliability:**
  - Selector fallback chain (`a.result__a`, `a.result__url`, `.result__title a`) and `BrowserSearchError` handling.
- **Security & Sandbox Integration:**
  - Registered high-risk tools (`browser_execute_js`, `browser_download_file`, cookie/storage writes) in `_risk_analyzer.py`, `_sandbox_manager.py`, and `config/security_policy.json`.
- **Tests & Documentation:**
  - Verified 224 unit tests passing under `testing/unit/modules/browser/`.
  - Updated `docs/07_Module_Design.md` and `docs/21_System_Contracts.md` (§27 Browser Port & Automation Contracts).

---

## [Phase 4.2] - PC Control Capability Expansion - 2026-08-02

### Added
- **System Settings group (`PCSystemSettings`):**
  - Wi-Fi: `wifi_set_power`, `wifi_get_power`, `wifi_list_networks`, `wifi_connect`.
  - Bluetooth: `bluetooth_set_power`, `bluetooth_get_power`, `bluetooth_list_devices`, `bluetooth_pair`.
  - Display: brightness, resolution (get/set/list), night light, and dark-mode toggles.
  - Power: airplane mode and Do-Not-Disturb get/set.
- **Software Management group (`PCSoftwareManager`):**
  - `software_list_installed`, `software_install`, `software_uninstall`, `software_check_update` via the native package manager (winget/apt/brew).
- **User Account Management group (`PCAccountManager`):**
  - `account_list_users`, `account_get_current_user`, `account_create_user`, `account_set_enabled`, `account_modify_groups`.
- **Architecture:**
  - Extended `PCControlPort` with 30 new abstract methods; `LocalPCControlAdapter` raises `PCControlNotImplementedError`.
  - `ProductionPCControlAdapter` dispatches per-OS via subprocess helpers with retry/permission/error mapping; new destructive operations added to `DANGEROUS_OPERATIONS`.
  - Added `PCControlExecutor` forwarding methods, `PCControlManager` public API, and new tool registrations (`pc_wifi`, `pc_bluetooth`, `pc_display`, `pc_system_settings`, `pc_software`, `pc_account`).
- **Security integration:**
  - New tools added to `_risk_analyzer.py` high/medium risk tables and `_sandbox_manager.py` allow/deny lists.
  - New `SecurityPolicyRule` entries in `config/security_policy.json` (confirm for software/display/settings, admin for account operations).
- **Tests:** 66 new unit tests under `testing/unit/modules/pc_control/test_new_capabilities.py`.

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
