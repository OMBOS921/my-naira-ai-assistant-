# 04. System Architecture

This document defines the architectural blueprints of the personal desktop AI Assistant (Naira-OS). It is designed to work efficiently on lightweight, low-resource hardware (Intel i3 6th Gen, 4GB RAM) while remaining highly scalable, modular, and future-proof.

---

## 1. Architectural Style: Micro-Kernel Pattern
To maintain high cohesion and loose coupling under strict RAM constraints, the project utilizes a **Micro-Kernel (Core-Plug) pattern** combined with **Clean Architecture (Domain-Driven boundaries)**.

* **The Core Kernel:** Comprises the central `Orchestrator`, `FastCommandRouter` (FCR Phase 2), `Security Manager`, `Configuration Manager`, and `Logger`. It occupies minimal memory (~50MB) and remains permanently running.
* **Plug-In/Service Modules:** High-overhead features (e.g., Voice, Vision, Browser Automation, 3D Avatar) are modeled as independent, dynamic services. They are imported and instantiated *only when activated* (Lazy Loading) and can be completely garbage-collected when idle.

---

## 2. The 6-Layer Clean Architecture Model
The system is divided into six distinct logical layers. Code dependencies flow strictly **downward** (downward-only dependency rule). No lower layer can import or depend on a higher layer.

```
 ┌────────────────────────────────────────────────────────┐
 │ 1. PRESENTATION LAYER (CLI terminal loop run_cli.py,   │
 │    FastAPI REST + WebSockets server main.py)           │
 └───────────────────────────┬────────────────────────────┘
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ 2. APPLICATION LAYER (Plugins, Feature Flags, Session) │
 └───────────────────────────┬────────────────────────────┘
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ 3. AI CORE LAYER (LLM routing, Master FCR Phase 2,     │
 │    CodingAgentManager w/ 24 Skill Packs, Context FSM)  │
 └───────────────────────────┬────────────────────────────┘
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ 4. SERVICE LAYER (TTS/STT, Screen Vision, Playwright   │
 │    Headless Browser, Proactive Watchdog)               │
 └───────────────────────────┬────────────────────────────┘
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ 5. INFRASTRUCTURE LAYER (SQLite Database, File stream, │
 │    LRU Response Cache with strict tool-call bypassing) │
 └───────────────────────────┬────────────────────────────┘
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ 6. OPERATING SYSTEM LAYER (Windows APIs, Raw OS system)│
 └───────────────────────────┴────────────────────────────┘
```

### Layer Definitions & Responsibilities

#### 1. Presentation Layer
* **Role:** Manages the input and output channels through which the user interacts with the system.
* **Components:**
  * **Interactive CLI Terminal Loop (`run_cli.py`):** Standalone local terminal runner supporting interactive prompt sessions and SIGINT graceful shutdown.
  * **FastAPI Server & WebSockets (`main.py`):** Real-time bi-directional `/ws/naira` endpoint handling `system_init` identity sync, speech barge-in interrupts, and UI streaming.
  * **System Tray Application Icon:** Minimal OS tray interface.

#### 2. Application Layer
* **Role:** Manages features, active sessions, and dynamically controls system capabilities.
* **Components:**
  * **Capability Manager:** Discovers, registers, and exposes dynamic modules at runtime.
  * **Feature Flag Manager:** Evaluates toggles to load or unload heavy packages based on RAM constraints.
  * **Session Manager & Conversation Manager:** Synchronizes multi-session state boundaries across WebSocket initialization and REST/CLI turns.
  * **Update Manager:** Safely handles version pulling and file patches without data corruption.

#### 3. AI Core Layer
* **Role:** Represents the cognitive brain of the assistant. Processes reasoning, manages history, orchestrates intent execution, and executes domain code tasks.
* **Components:**
  * **Core Orchestrator:** The mediator/FSM (`FSMState`) that controls request life-cycles.
  * **Master Fast Command Router (FCR Phase 2):** High-speed deterministic command interceptor utilizing phrase matching and dynamic length-weighted candidate scoring (< 5ms response time).
  * **LLM Manager:** Dynamic gateway wrapper for providers (Gemini, Ollama, DeepSeek) with fallback orchestration and LRU caching (tool-call responses bypass cache).
  * **CodingAgentManager & 24 Skill Packs:** Domain-specific skill pack ecosystem (Python, C, C++, Next.js, FastAPI, Docker, React, Node.js, DSA, Competitive Programming, DevOps, Kubernetes, Linux, MongoDB, PostgreSQL, SQL, Web Security, Git, etc.) with automated code verification pipelines.
  * **Prompt Manager & Context Manager:** Handles strict text templates and sliding-window context token management.

#### 4. Service Layer
* **Role:** Wraps heavy hardware execution engines and background monitoring into standard interfaces.
* **Components:**
  * Speech-to-Text (Whisper wrapper)
  * Text-to-Speech (pyttsx3 wrapper)
  * Screen grabbing & Vision scanner (OpenCV/PIL wrapper)
  * Headless Browser Automation engine (Playwright adapter operating without physical OS tab popups)
  * **Proactive Watchdog (`ProactiveWatchdog`):** Background system vitals engine monitoring CPU/RAM spikes with throwaway warm-up sampling and voice alert synthesis.

#### 5. Infrastructure Layer
* **Role:** Concrete adapters for external database storage, file streams, system logs, and response caching.
* **Components:**
  * **Memory Manager (SQLite Client):** Stores persistent conversations and logs.
  * **LLM Response Cache:** In-memory LRU cache with TTL expiration. Skips caching any responses containing `tool_calls`.
  * Local File-Index (Vector database for local semantic memories).
  * Buffered File Logger (Writes logs sequentially to conserve CPU).

#### 6. Operating System Layer
* **Role:** Direct interface with the Windows OS and physical devices.
* **Components:**
  * File System paths (`C:\Users\...`)
  * Sound drivers (Microphone input, Audio speaker output)
  * PC Control Manager (`pyautogui`, `psutil`, `pywin32`)
  * Local process manager

---

## 3. Communication Patterns

### A. Fast Command Routing & Mediator Pattern for Execution
For incoming requests, the **Master Fast Command Router (FCR Phase 2)** first attempts deterministic phrase matching with dynamic length-weighted candidate scoring. If a command matches an OS intent, it executes directly with sub-5ms latency.

If FCR does not match, the **Core Orchestrator** mediates LLM inference, tool resolution, and response delivery:

```
[User Request (CLI / WS)] ──► [Master FCR Phase 2] ──(No match)──► [Orchestrator]
                                   │                                    │
                            (Direct Match < 5ms)                [LLM / Tool Router]
                                   │                                    │
                                   ▼                                    ▼
                         [PC Control / Action]                 [Coding Agent / Tools]
```

### B. Event-Bus for Asynchronous Pub/Sub
For non-blocking status updates, a lightweight asynchronous Event Bus is used.
* **Example:** When system RAM or CPU usage breaches thresholds, the Proactive Watchdog emits a `watchdog.alert` event. The Event Bus relays this to the Orchestrator, which broadcasts a synthesized voice alert to connected WebSockets.

---

## 4. Hardware Optimization & Reliability Tactics
To run smoothly on an **Intel i3 with 4GB RAM**:
1. **Dynamic Garbage Collection:** The Core explicitly invokes `gc.collect()` after unloading heavy tasks.
2. **Tool-Call Cache Safeguards:** LLM Response Cache blindly skipping cached tool calls ensures destructive actions are never re-executed without reasoning.
3. **Sequential Queue (Job Manager):** Background jobs process in single-threaded task queues to prevent CPU thread starvation.
4. **Comprehensive System Testing:** Verified with 100-Scenario System E2E Regression Suite and 100-Scenario Coding Agent Regression Suite (strict physical OS verification, 0 false positives).

---

## 5. Remote Bridge Infrastructure & Android Gateway

Phase 4.1 introduces the **Remote Bridge Infrastructure**, enabling secure, encrypted out-of-network remote control and status synchronization between the Naira-OS desktop core and remote Android clients over an Ngrok WebSocket tunnel with Firebase Cloud Messaging (FCM) silent wake-up.

### Components & Subsystems

1. **FCM Wake-Up Dispatcher (`FCMDispatcher`):**
   * Located at [`fcm_manager.py`](file:///c:/Users/user/Desktop/Project-AIF-main/backend/modules/remote_bridge/fcm_manager.py).
   * Initializes Firebase Admin SDK using local credentials (`firebase_credentials.json`).
   * Dispatches high-priority (`priority="high"`, `ttl=3600`) silent data-only FCM push notifications to wake remote Android devices from Doze mode.
   * Transmits the current Ngrok WebSocket tunnel URI (`wss://.../ws/remote`) in the push payload.

2. **Ngrok WebSocket Router (`remote_router.py`):**
   * Located at [`remote_router.py`](file:///c:/Users/user/Desktop/Project-AIF-main/backend/modules/remote_bridge/remote_router.py).
   * Exposes the `@router.websocket("/ws/remote")` endpoint over the public Ngrok tunnel.
   * Manages connection authentication, cryptographic handshake validation, and active WebSocket connection tracking via `RemoteBridgeManager`.

3. **Offline Action Queue (`OfflineActionQueue`):**
   * Located at [`remote_router.py`](file:///c:/Users/user/Desktop/Project-AIF-main/backend/modules/remote_bridge/remote_router.py).
   * Thread-safe async in-memory queue holding cryptographically signed command payloads when the target mobile device is offline or disconnected.
   * Automatically flushes and broadcasts queued commands over the WebSocket connection as soon as the client authenticates upon re-connection.

4. **Cryptographic Security & Risk Engine (`SecurityRegistrar` & `RiskEngine`):**
   * Located at [`bridge_security.py`](file:///c:/Users/user/Desktop/Project-AIF-main/backend/modules/remote_bridge/bridge_security.py).
   * Computes HMAC-SHA256 signatures for outgoing/incoming action payloads with ISO-8601 timestamps and 16-byte random hex nonces.
   * Evaluates action risk scores (0–100); enforces mandatory biometric verification when action risk score exceeds threshold (`score > 80`).

### Android Remote Bridge Architectural Diagram

```text
┌───────────────────────────────────────────────────────────────────────────┐
│                          Naira-OS Core Backend                            │
│                                                                           │
│   ┌──────────────────────┐  ┌─────────────────────┐  ┌──────────────────┐ │
│   │ SecurityRegistrar &  │  │ RemoteBridgeManager │  │  FCMDispatcher   │ │
│   │     RiskEngine       │  │ & OfflineActionQueue│  │  (fcm_manager)   │ │
│   └──────────┬───────────┘  └──────────┬──────────┘  └────────┬─────────┘ │
└──────────────┼─────────────────────────┼──────────────────────┼───────────┘
               │                         │                      │
               │                         │ Send Wakeup Ping     │ (FCM Push Payload)
               │                         │                      ▼
               │                         │             ┌──────────────────┐
               │                         │             │ Google FCM Cloud │
               │                         │             └────────┬─────────┘
               │                         │                      │ Silent Wakeup
               │                         │                      ▼
               │             ┌───────────┴───────────┐ ┌──────────────────┐
               │             │  Ngrok WS Router      │ │  Android Device  │
               │             │  (/ws/remote endpoint)│ │   (Doze Mode)    │
               │             └───────────┬───────────┘ └────────┬─────────┘
               │                         │                      │ Device Wakes Up
               │   Encrypted WebSocket   │                      │ & Connects WS
               └─────────────────────────┼──────────────────────┘
                                         ▼
                             ┌───────────────────────┐
                             │   Android Remote App  │
                             │  & Security Vault     │
                             └───────────────────────┘
```

