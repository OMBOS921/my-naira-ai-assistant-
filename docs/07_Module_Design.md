# 07. Module Design & Specifications

This document defines the strict boundaries, single responsibilities, and lightweight design considerations of all primary modules inside the Naira-OS.

---

## 1. Application Layer Modules

### A. Capability Manager
* **Module Location:** `backend/modules/capability/`
* **Purpose:** Handles runtime registration, capability discovery, and dynamic routing boundaries.
* **Responsibilities:**
  * Registers dynamic capabilities offered by active plugins or core services.
  * Checks if a requested feature is registered before dispatching commands.
  * Allows elegant degradation if a component fails to load (Graceful Degradation).
* **RAM Optimization:** Stores index references in a lightweight flat python `dict`, requiring negligible memory.

### B. Feature Flag Manager
* **Module Location:** `backend/modules/settings/`
* **Purpose:** Manages performance-based feature toggles to prevent RAM starvation.
* **Responsibilities:**
  * Checks configuration parameters to determine if dynamic services (e.g., 3D Avatar, Real-time Vision OCR) should load.
  * Dynamically bypasses imports of heavy third-party packages if resources are constrained.
* **RAM Optimization:** Acts as a gatekeeper; avoids importing heavy frameworks (like PyTorch or OpenCV) entirely if flags are toggled `False`.

### C. Session Manager
* **Module Location:** `backend/modules/session/`
* **Purpose:** Tracks active user interaction loops and security authorization periods.
* **Responsibilities:**
  * Maintains conversation history session tokens.
  * Tracks security approval states (e.g., "Permissions granted to PC Control for next 10 minutes").
  * Limits context token footprint to prevent context window bloating.

### D. Update Manager
* **Module Location:** `backend/modules/update/` (Phase 6)
* **Purpose:** Ensures secure, non-destructive, lifetime system updates.
* **Responsibilities:**
  * Checks and pulls local version patches from Git safely.
  * Protects local user data, persistent settings, and database tables from being overwritten or corrupted.
  * Schedules automated schema migrations for databases.

### E. Local Telemetry Manager
* **Module Location:** `backend/modules/telemetry/` (Phase 6)
* **Purpose:** Performs privacy-safe, offline performance benchmarking.
* **Responsibilities:**
  * **Strict Offline Constraint:** Writes all diagnostic logs ONLY to the local filesystem. No external cloud endpoints.
  * Monitors API latency (e.g., Gemini API call duration) and local system memory usage.
  * Alerts the user if RAM consumption exceeds 85%, suggesting system adjustments (e.g., lower camera sample frequency).

---

## 2. AI Core Layer Modules

### A. Core Orchestrator
* **Purpose:** The central mediator of the entire assistant.
* **Responsibilities:**
  * Receives processed user input from the Presentation layer.
  * Controls system states using a strict Finite State Machine (`BOOTING`, `IDLE`, `LISTENING`, `PROCESSING`, `SPEAKING`, `SHUTDOWN`). Extended states are defined in `18_Boot_Sequence.md`.
  * Dispatches events to the internal Event Bus and coordinates response flows.

### B. LLM Manager
* **Purpose:** Decouples the assistant from any specific LLM provider.
* **Responsibilities:**
  * Exposes a unified inference API (e.g., `generate_response(prompt: str, context: list) -> str`).
  * Seamlessly switches backend providers (Gemini, OpenAI, Ollama, DeepSeek) through configuration modifications.
  * Automatically retries on API timeouts or switches to secondary offline modes.

### C. Prompt Manager
* **Purpose:** Standardizes, compiles, and optimizes prompts sent to LLMs.
* **Responsibilities:**
  * Stores structural system instructions as plain text templates outside code files.
  * Compiles variables (such as active file lists or system variables) dynamically into clean prompts.

### D. Context Manager
* **Purpose:** Prevents token footprint bloat.
* **Responsibilities:**
  * Performs sliding window context compression based on active token counts.
  * Extracts high-level semantic keywords from old conversations to store in Long-Term Memory.

---

## 3. Service Layer Modules

### A. Voice Module (TTS & STT)
* **Purpose:** Handles physical conversation mechanisms.
* **Responsibilities:**
  * **STT (Speech-to-Text):** Runs Whisper models locally with low sampling to transcribe user speech.
  * **TTS (Text-to-Speech):** Utilizes offline `pyttsx3` (zero-memory overhead) or highly optimized local tools to synthesize responses.
  * Implements dynamic voice thresholding to avoid continuous background noise recording.

### B. Vision Module
* **Purpose:** Coordinates screenshot capturing, image processing, and OCR.
* **Responsibilities:**
  * Captures screen contents safely when explicitly requested.
  * Uses lightweight OCR wrappers and relies on Gemini Vision API for deep visual understanding to keep local CPU processing low.

### C. Browser Module
* **Purpose:** Automates dynamic web-searches and actions.
* **Responsibilities:**
  * Uses headless, lightweight scraper mechanisms (e.g., Playwright) to retrieve search contexts.
  * Lazily loads browser drivers only during active scraping cycles to save ~250MB RAM when idle.

### D. PC Control & File Manager Modules
* **Purpose:** Safe OS automation wrappers.
* **Responsibilities:**
  * Performs local automation actions (launching approved apps, modifying files within restricted user directories).
  * Enforces sandboxed paths; blocks any modifications to Windows system directories or standard registries.

---

## 4. Presentation Layer Modules

### A. Avatar Module (Phase 6 — Placeholder)

* **Module Location:** `backend/modules/avatar/`
* **Purpose:** Provides an IPC bridge between the Naira-OS core and an external 3D rendering engine (Unity, Godot, or custom renderer).
* **Layer:** Presentation Layer (Layer 1)
* **Responsibilities:**
  * Opens and manages a socket or named-pipe connection to the external renderer.
  * Relays character state data (emotion, speech animation, pose) from the Orchestrator to the renderer.
  * Receives user interaction events from the renderer and forwards them to the Orchestrator.
* **Constraint:** The avatar module must not perform AI inference, access the database, or execute system commands. All data is opaque payloads; interpretation is the Orchestrator's responsibility.
* **RAM Optimization:** The renderer runs as a separate process. The Python module itself handles only socket I/O. The module is lazy-loaded and implemented when Phase 6 begins.
