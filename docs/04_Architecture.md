# 04. System Architecture

This document defines the architectural blueprints of the personal desktop AI Assistant (Naira-OS). It is designed to work efficiently on lightweight, low-resource hardware (Intel i3 6th Gen, 4GB RAM) while remaining highly scalable, modular, and future-proof.

---

## 1. Architectural Style: Micro-Kernel Pattern
To maintain high cohesion and loose coupling under strict RAM constraints, the project utilizes a **Micro-Kernel (Core-Plug) pattern** combined with **Clean Architecture (Domain-Driven boundaries)**.

* **The Core Kernel:** Comprises the central `Orchestrator`, `Security Manager`, `Configuration Manager`, and `Logger`. It occupies minimal memory (~50MB) and remains permanently running.
* **Plug-In/Service Modules:** High-overhead features (e.g., Voice, Vision, Browser Automation, 3D Avatar) are modeled as independent, dynamic services. They are imported and instantiated *only when activated* (Lazy Loading) and can be completely garbage-collected when idle.

---

## 2. The 6-Layer Clean Architecture Model
The system is divided into six distinct logical layers. Code dependencies flow strictly **downward** (downward-only dependency rule). No lower layer can import or depend on a higher layer.

```
 ┌────────────────────────────────────────────────────────┐
 │ 1. PRESENTATION LAYER (CLI, Web UI, WebSocket Server)  │
 └───────────────────────────┬────────────────────────────┘
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ 2. APPLICATION LAYER (Plugins, Feature Flags, Session) │
 └───────────────────────────┬────────────────────────────┘
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ 3. AI CORE LAYER (LLM routing, Prompting, Context FSM) │
 └───────────────────────────┬────────────────────────────┘
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ 4. SERVICE LAYER (TTS/STT, OCR, Screen Capture, Web)   │
 └───────────────────────────┬────────────────────────────┘
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ 5. INFRASTRUCTURE LAYER (SQLite Database, File stream) │
 └───────────────────────────┬────────────────────────────┘
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ 6. OPERATING SYSTEM LAYER (Windows APIs, Raw OS system)│
 └────────────────────────────────────────────────────────┘
```

### Layer Definitions & Responsibilities

### 1. Presentation Layer
* **Role:** Manages the input and output channels through which the user interacts with the system.
* **Components:**
  * Interactive CLI console
  * Local WebSocket servers (for local React UI and 3D Avatar interface)
  * System Tray application icon
* **Constraint:** No business logic or AI prompt processing occurs here.

### 2. Application Layer
* **Role:** Manages features, active sessions, and dynamically controls system capabilities.
* **Components:**
  * **Capability Manager:** Discovers, registers, and exposes dynamic modules at runtime.
  * **Feature Flag Manager:** Evaluates toggles to load or unload heavy packages based on RAM constraints.
  * **Session Manager:** Tracks active session tokens and user state boundaries.
  * **Update Manager:** Safely handles version pulling and file patches without data corruption.

### 3. AI Core Layer
* **Role:** Represents the cognitive brain of the assistant. Processes reasoning, manages history, and orchestrates intent execution.
* **Components:**
  * **Core Orchestrator:** The mediator/FSM that controls request life-cycles.
  * **LLM Manager:** Dynamic gateway wrapper for APIs (Gemini, Ollama, DeepSeek).
  * **Prompt Manager:** Handles strict text templates.
  * **Context Manager:** Optimizes token window allocation and sliding histories.

### 4. Service Layer
* **Role:** Wraps heavy hardware execution engines into standard interfaces.
* **Components:**
  * Speech-to-Text (Whisper wrapper)
  * Text-to-Speech (pyttsx3 wrapper)
  * Screen grabbing / OCR utilities (OpenCV wrapper)
  * Browser automation engine

### 5. Infrastructure Layer
* **Role:** Concrete adapters for external database storage, file streams, and system logs.
* **Components:**
  * **Memory Manager (SQLite Client):** Stores persistent conversations and logs.
  * Local File-Index (Vector database for local semantic memories).
  * Buffered File Logger (Writes logs sequentially to conserve CPU).

### 6. Operating System Layer
* **Role:** Direct interface with the Windows OS and physical devices.
* **Components:**
  * File System paths (`C:\Users\...`)
  * Sound drivers (Microphone input, Audio speaker output)
  * Keyboard & Mouse automation hooks (`pyautogui`)
  * Local process manager

---

## 3. Communication Patterns

### A. Mediator Pattern for Request Execution
For critical sequential actions (such as answering a prompt or running a script), the **Core Orchestrator** acts as a central mediator. Modules do not call each other directly; instead, they exchange data through the Orchestrator.

```
[User Request] ──► [Orchestrator] ──► [Security Filter] ──► [LLM routing] ──► [PC Control]
```

### B. Event-Bus for Asynchronous Pub/Sub
For non-blocking status updates, a lightweight asynchronous Event Bus is used.
* **Example:** When the battery level is low, the OS layer fires a `system_battery_low` event. The Event Bus relays this to the Orchestrator, which notifies the user.

---

## 4. Hardware Optimization Tactics
To run smoothly on an **Intel i3 with 4GB RAM**:
1. **Dynamic Garbage Collection:** The Core explicitly invokes `gc.collect()` after unloading heavy tasks (e.g., dynamic vision processing).
2. **Sequential Queue (Job Manager):** Background jobs are processed in a single-threaded task queue to prevent concurrent CPU thread starvation on the dual-core i3 processor.
3. **No Heavy Vector Servers:** Local Vector indices are built using lightweight Numpy/JSON indexes rather than launching a background dockerized ChromaDB instance.
