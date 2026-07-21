# 13. Project Development Roadmap

This document structures the milestones, phase-wise deliverables, and lifecycle progression of the personal desktop AI Assistant (Naira-OS).

---

## Roadmap Phases Overview

```text
 ┌────────────────────────────────────────────────────────┐
 │ PHASE 0.5: ARCHITECTURAL BLUEPRINT (Current Phase)     │
 └───────────────────────────┬────────────────────────────┘
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ PHASE 1: CORE FOUNDATION & CONFIG SETUP (Next Phase)   │
 └───────────────────────────┬────────────────────────────┘
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ PHASE 2: LOCAL MEMORY & CONTEXT PIPELINE               │
 └───────────────────────────┬────────────────────────────┘
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ PHASE 3: VOICE & INTERACTIVE SYSTEM CLI                │
 └───────────────────────────┬────────────────────────────┘
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ PHASE 4: SANDBOXED PC CONTROL & FILE AUTOMATION        │
 └───────────────────────────┬────────────────────────────┘
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ PHASE 5: MULTIMODAL SCREEN VISION INTEGRATION          │
 └───────────────────────────┬────────────────────────────┘
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ PHASE 6: PRODUCTION HARDENING & PLUGINS                │
 └────────────────────────────────────────────────────────┘
```

---

## 1. Phase Details

### Phase 0.5: Architectural Blueprint & Specifications (Completed)
* **Goal:** Finalize architecture layers, establish directory design, define module separation contracts, and agree on low-end hardware performance rules.
* **Deliverables:**
  * System Architecture Guide (`04_Architecture.md`)
  * Folder Structure Layout Specifications (`06_Folder_Structure.md`)
  * Submodule Design Requirements (`07_Module_Design.md`)
  * Security Sandbox Guidelines (`09_Security.md`)

---

### Phase 1: Core Foundation & Config Setup (Upcoming)
* **Goal:** Set up safe environment configuration variables, daily buffered logging streams, and bootstrap the core Orchestrator event loop (`asyncio`).
* **Deliverables:**
  * Root environment bootstrap configuration template (`.env.example` / `.env`).
  * Non-blocking, thread-safe daily rotating file Logger.
  * Active Configuration Parser & Manager with dynamic verification.
  * Bare-bone Orchestrator initialization with basic console CLI loop.

---

### Phase 2: Local Memory & Context Pipeline
* **Goal:** Enable short-term conversational context tracking and local persistent SQLite databases for long-term metadata caching.
* **Deliverables:**
  * Memory SQLite client manager.
  * Context Window Token Sliding/Compression handlers.
  * Basic Local file keyword storage for lightweight semantic indexing.

---

### Phase 3: Voice & Interactive System CLI
* **Goal:** Implement offline Speech-To-Text and Text-To-Speech capabilities without background resource leaking.
* **Deliverables:**
  * Offline Text-to-Speech adapter (`pyttsx3`).
  * Dynamic microphone voice sampler & transcription controller (`Whisper`).
  * Comprehensive interactive console UI showing current state machine logs.

---

### Phase 4: Sandboxed PC Control & File Automation
* **Goal:** Integrate secure, permission-validated Windows command execution and safe path operations.
* **Deliverables:**
  * Secure Permission Gatekeeper popup dialog/CLI verify block.
  * Sandboxed File management adapter (Read, Write, Create inside designated user paths).
  * System API wrappers (Process starting and terminating engines).

---

### Phase 5: Multimodal Screen Vision Integration
* **Goal:** Provide image and UI screenshot analyzing capabilities using Gemini 1.5 APIs.
* **Deliverables:**
  * Async Screen screenshot grabber (Dynamic low-frequency capture).
  * Multimodal LLM prompt compiler for image contexts.
  * OCR post-processing layout scanner.

---

### Phase 6: Production Hardening, 3D Avatar, & Plugins
* **Goal:** Bring the system up to lifelong scalability standards by decoupling user interfaces and introducing dynamic custom plugin interfaces.
* **Deliverables:**
  * Local WebSocket communication gateway (Presentation boundary).
  * Dynamic Plugin Manager (Load, Enable, Disable, Purge lifecycles).
  * Unity/Godot 3D Anime Avatar IPC link wrapper.
  * Diagnostic Local Telemetry Analyzer Dashboard.
