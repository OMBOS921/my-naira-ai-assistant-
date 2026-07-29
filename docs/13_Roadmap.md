# 13. Project Development Roadmap

This document structures the milestones, phase-wise deliverables, and lifecycle progression of the personal desktop AI Assistant (Naira-OS).

---

## Roadmap Phases Overview

```text
 ┌────────────────────────────────────────────────────────┐
 │ PHASE 0.5: ARCHITECTURAL BLUEPRINT (Completed)         │
 └───────────────────────────┬────────────────────────────┘
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ PHASE 1: CORE FOUNDATION & CONFIG SETUP (Completed)    │
 └───────────────────────────┬────────────────────────────┘
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ PHASE 2: MASTER FAST COMMAND ROUTER (FCR) (Completed)  │
 └───────────────────────────┬────────────────────────────┘
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ PHASE 3: INTERACTIVE CLI & WEBSOCKET GATEWAY(Completed)│
 └───────────────────────────┬────────────────────────────┘
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ PHASE 4: PROACTIVE WATCHDOG & LLM CACHING (Completed)  │
 └───────────────────────────┬────────────────────────────┘
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ PHASE 5: CODING AGENT & 24 SKILL PACKS (Completed)     │
 └───────────────────────────┬────────────────────────────┘
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ PHASE 5.1: GRAND UNIFIED PATCH & CLI RUNNER(Completed) │
 └───────────────────────────┬────────────────────────────┘
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ PHASE 6: PRODUCTION HARDENING & EXTENSION ECOSYSTEM    │
 └────────────────────────────────────────────────────────┘
```

---

## 1. Phase Details

### Phase 0.5: Architectural Blueprint & Specifications (Completed)
* **Goal:** Finalize architecture layers, establish directory design, define module separation contracts, and agree on low-end hardware performance rules.
* **Deliverables:**
  * System Architecture Guide (`04_Architecture.md`)
  * Tech Stack Specifications (`05_Tech_Stack.md`)
  * Folder Structure Specifications (`06_Folder_Structure.md`)
  * Submodule Design Requirements (`07_Module_Design.md`)
  * Security Sandbox Guidelines (`09_Security.md`)

---

### Phase 1: Core Foundation & Config Setup (Completed)
* **Goal:** Set up safe environment configuration variables, daily buffered logging streams, and bootstrap the core Orchestrator event loop (`asyncio`).
* **Deliverables:**
  * Root environment bootstrap configuration template (`.env.example` / `.env`).
  * Non-blocking, thread-safe daily rotating file Logger.
  * Active Configuration Parser & Manager with dynamic `EnvironmentSnapshot` verification.
  * Core Orchestrator initialization with standard dependency injection (`DIContainer`).

---

### Phase 2: Master Fast Command Router (FCR Phase 2) & Memory Pipeline (Completed)
* **Goal:** Implement sub-5ms deterministic command routing and short/long-term session context tracking.
* **Deliverables:**
  * Master Fast Command Router (FCR Phase 2) with phrase matching and dynamic length-weighted candidate scoring.
  * Memory SQLite client manager and Context Window Token Sliding handlers.
  * Local keyword storage for lightweight semantic indexing.

---

### Phase 3: Interactive CLI & WebSocket Gateway (Completed)
* **Goal:** Provide presentation entrypoints for both command-line terminal power users and Web UI clients.
* **Deliverables:**
  * Real-time FastAPI WebSocket endpoint (`/ws/naira`) supporting `system_init` identity sync and barge-in audio interrupts.
  * Standalone CLI Terminal loop (`run_cli.py`) with non-blocking stdin reader and clean signal handlers.
  * Presentation layer decoupling from backend domain logic.

---

### Phase 4: Proactive Watchdog & LLM Caching Reliability (Completed)
* **Goal:** Equip Naira-OS with autonomous system health monitoring and reliable LLM response caching safeguards.
* **Deliverables:**
  * `ProactiveWatchdog` engine checking CPU/RAM metrics with initial throwaway warm-up sampling and voice alert synthesis.
  * LLM Response Cache (`LLMResponseCache`) with strict tool-call bypassing to eliminate destructive action replay risks.
  * Dynamic provider fallback chain (Gemini → Ollama → DeepSeek).

---

### Phase 5: Coding Agent Subsystem & 24 Skill Packs (Completed)
* **Goal:** Build an autonomous coding agent capable of multi-language project analysis, execution planning, code generation, refactoring, debugging, and code review.
* **Deliverables:**
  * `CodingAgentManager` engine and `ProjectAnalyzerProvider` (detecting Python, JS, TS, JSX, TSX, Go, Rust, Java, C, C++, C#).
  * 24 specialized Skill Packs covering Python, C, C++, Java, JS, TS, React, Next.js, Node.js, Express, FastAPI, Django, DSA, Competitive Programming, AI/ML, Docker, Kubernetes, DevOps, Linux, PostgreSQL, MongoDB, SQL, Web Security, Git.
  * 100-Scenario Coding Agent Regression Suite passing with 0 false positives.

---

### Phase 5.1: The Grand Unified Patch & CLI Entrypoint (Completed)
* **Goal:** Execute surgical logic fixes identified in multi-AI audit and deliver missing CLI runner.
* **Deliverables:**
  * **Browser Fix:** Headless operation without physical browser tab popups.
  * **React/Next.js Fix:** Support for `.jsx` and `.tsx` file analysis in project structure analyzer.
  * **Tool-Call Replay Fix:** Strict cache exclusion for responses containing `tool_calls`.
  * **CPU Warm-up Fix:** `psutil.cpu_percent` warm-up sampling in watchdog.
  * **Session Consistency Fix:** WebSocket `system_init` explicitly syncing `SessionManager`, `ConversationManager`, and `InteractionManager` state.
  * **CLI Runner:** Production-ready `run_cli.py` terminal entrypoint.
  * 100-Scenario System E2E Suite passing cleanly.

---

### Phase 6: Production Hardening & Extension Ecosystem (Active / Upcoming)
* **Goal:** Expand plugin ecosystem, refine 3D Avatar IPC link, and optimize background multi-agent orchestrations.
* **Deliverables:**
  * Dynamic Plugin Manager (Load, Enable, Disable, Purge lifecycles).
  * Unity/Godot 3D Anime Avatar IPC link wrapper.
  * Advanced Multi-Agent collaboration network.
