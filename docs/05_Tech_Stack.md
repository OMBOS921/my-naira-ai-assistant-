# 05. Technology Stack Specifications

This document outlines the core technology stack, libraries, framework selections, and runtime dependencies powering Naira-OS.

---

## 1. Core Runtime & Language Specification

* **Primary Language:** Python 3.12+ (Compatible with Python 3.14.x)
* **Asynchronous Engine:** Native Python `asyncio` event loop with async/await coroutines.
* **Type Safety:** Python type hints (`__future__.annotations`, `dataclasses`, `typing`).
* **Environment Configuration:** `python-dotenv` with dynamic `EnvironmentSnapshot` validation.

---

## 2. Presentation Layer & Gateway

* **Web Framework:** FastAPI (ASGI application backend).
* **ASGI Web Server:** Uvicorn (`uvicorn.run("main:app")`).
* **WebSockets Engine:** Native FastAPI WebSocket router (`/ws/naira`) supporting real-time bi-directional streaming, `system_init` identity synchronization, and speech barge-in interrupts.
* **CLI Terminal Entrypoint (`run_cli.py`):** Standalone terminal interface runner supporting non-blocking `asyncio.to_thread` console input loops and signal handling.
* **Frontend Web Interface:** React / Vanilla JavaScript frontend with dynamic CSS components, glassmorphism design, and 3D Avatar IPC integration.

---

## 3. Intelligence & AI Routing Layer

* **Primary LLM SDK:** Google GenAI SDK (`google-genai`).
* **LLM Providers:**
  * **Gemini:** Primary Cloud LLM (`gemini-2.5-flash` / `gemini-1.5-flash`).
  * **Ollama:** Local fallback LLM server integration.
  * **DeepSeek:** Secondary fallback provider integration.
* **Fallback Orchestration:** `LLMProviderOrchestrator` fallback chain across registered providers.
* **LLM Caching System:** `LLMResponseCache` — Fast in-memory LRU cache with SHA-256 key hashing and TTL expiration. Strict rule: Queries producing `tool_calls` bypass cache to eliminate tool replay risks.

---

## 4. Deterministic Command Routing & Runtime

* **Master Fast Command Router (FCR Phase 2):** High-speed phrase-matching router with length-weighted candidate scoring for OS controls, application launching, and volume/brightness actions (< 5ms latency).
* **Human Interaction Layer:** `InteractionManager` (v2.0) featuring 4-level Response Priority classification (`CRITICAL`, `ACTION`, `CONVERSATION`, `BACKGROUND`), atomic cancellation, personality profiles (`professional`, `friendly`, `close_friend`, `minimal`), and speech readiness transformers.
* **Session & State Managers:** `SessionManager` and `ConversationManager` providing multi-session isolation and sliding-window context token budget management.
* **Proactive Watchdog:** `ProactiveWatchdog` engine measuring CPU and RAM vitals using `psutil` with initial warm-up sampling and voice alert synthesis.

---

## 5. Coding Agent Subsystem

* **Manager:** `CodingAgentManager` providing automated code analysis, planning, code generation, refactoring, debugging, and review.
* **24 Dedicated Skill Packs:**
  1. Python (`python_expert.py`)
  2. C (`c_expert.py`)
  3. C++ (`cpp_expert.py`)
  4. Java (`java_expert.py`)
  5. JavaScript (`javascript_expert.py`)
  6. TypeScript (`typescript_expert.py`)
  7. React (`react_expert.py`)
  8. Next.js (`nextjs_expert.py`)
  9. Node.js (`nodejs_expert.py`)
  10. Express (`express_expert.py`)
  11. FastAPI (`fastapi_expert.py`)
  12. Django (`django_expert.py`)
  13. Data Structures & Algorithms (`dsa_expert.py`)
  14. Competitive Programming (`competitive_programming_expert.py`)
  15. AI & ML (`ai_ml_expert.py`)
  16. Docker (`docker_expert.py`)
  17. Kubernetes (`kubernetes_expert.py`)
  18. DevOps (`devops_expert.py`)
  19. Linux (`linux_expert.py`)
  20. PostgreSQL (`postgresql_expert.py`)
  21. MongoDB (`mongodb_expert.py`)
  22. SQL (`sql_expert.py`)
  23. Web Security (`web_security_expert.py`)
  24. Git (`git_expert.py`)
* **Project Analyzer:** `DefaultProjectAnalyzerProvider` with multi-language detection including `.py`, `.js`, `.ts`, `.jsx`, `.tsx`, `.go`, `.rs`, `.java`, `.cpp`, `.c`, `.cs`.

---

## 6. Service & Automation Adapters

* **Browser Automation:** `PlaywrightBrowserAdapter` with headless execution (webbrowser popups disabled for silent operation).
* **PC Control:** `pyautogui`, `psutil`, `pywin32` adapters for desktop system control.
* **Text-to-Speech (TTS):** `pyttsx3` offline speech synthesis engine.
* **Speech-to-Text (STT):** Whisper voice transcription adapter.
* **Vision & OCR:** PIL (Pillow) screen grabber and OpenCV image processing wrappers.

---

## 7. Testing & Quality Assurance

* **Testing Framework:** `pytest` & `pytest-asyncio`.
* **System E2E Regression Suite:** 100-Scenario System E2E test suite verifying physical OS state, system initialization, and execution paths with 0 false positives.
* **Coding Agent Suite:** 100-Scenario Coding Agent test suite validating all 24 Skill Packs across complex project operations.
