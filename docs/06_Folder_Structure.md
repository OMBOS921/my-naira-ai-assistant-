# 06. Folder Structure & Directory Responsibilities

This document outlines the professional directory structure for the personal desktop AI Assistant (Naira-OS). It aligns with the 6-layer architecture model, ensuring separation of concerns, high cohesion, and loose coupling.

---

## 1. Directory Tree Overview

```text
AI_Assistant/
├── .env                  # Confidential API keys and credentials
├── .env.example          # Non-confidential environment template
├── .gitignore            # Git exclusion rules
├── LICENSE               # Open-source or private license terms
├── README.md             # Project quick-start and setup guide
├── requirements.txt      # Lightweight external dependencies
├── main.py               # Main application entry point & Event loop bootstrap
├── config/               # Configuration files (YAML / JSON)
├── docs/                 # Lifetime knowledge base documentation
├── logs/                 # Active file logger directory (Daily rotating files)
├── backend/              # Central logical core codebase (The Python package)
│   ├── __init__.py
│   ├── orchestrator.py   # State FSM, Request router & Event-bus mediator
│   └── modules/          # Dynamic sub-modules (Single Responsibility)
│       ├── __init__.py
│       ├── llm/          # Dynamic LLM Provider Wrappers (Gemini, Ollama, etc.)
│       ├── prompt/       # Static templates & prompt compilation
│       ├── context/      # Token calculation & sliding window managers
│       ├── memory/       # SQLite handlers & local key/value caches
│       ├── security/     # Payload sanitizers, regex validation engines
│       ├── permissions/  # Blocking user approval prompts / CLI Dialogs
│       ├── pc_control/   # OS automation adapters (GUI Automation, App execution)
│       ├── file_manager/ # Safe sandboxed file operations (Copy, Read, Write)
│       ├── browser/      # Headless lightweight web scrapers
│       ├── capability/   # Capability discovery, registration & command routing
│       ├── session/      # Session state & security token tracking
│       ├── vision/       # Lazy-loaded snapshot OCR wrappers
│       ├── voice/        # Pyttsx3 TTS & Whisper offline STT wrappers
│       ├── plugin/       # Extension framework & hook registries (Phase 6)
│       ├── avatar/       # Socket/TCP hooks to external 3D rendering engine (Phase 6)
│       ├── settings/     # User profile metadata, configuration & feature flags
│       ├── telemetry/    # Offline performance monitoring & diagnostics (Phase 6)
│       ├── update/       # Secure self-update & schema migration engine (Phase 6)
│       └── utils/        # Common reusable functions (DateTime, Path conversions)
└── testing/              # Independent Test Suites (Isolated from runtime packages)
    ├── unit/             # Isolated sub-module test suites (PyTest specs)
    └── integration/      # System Integration and Flow Verification specs
```

---

## 2. Directory Responsibilities

### Root Directory (`/`)
* **`main.py`:** Initializes the Event Loop (`asyncio`), sets up basic OS parameters, loads settings, and launches the central core.
* **`.env` / `.env.example`:** Holds developer secrets securely. Never committed to version control.
* **`requirements.txt`:** Lists pinned, lightweight, audited external packages (e.g., `google-generativeai`, `pyttsx3`, `pytest`).

### Backend Core Codebase (`/backend/`)
* **`orchestrator.py`:** Coordinates request pipelines, registers active capabilities, manages global system states (`BOOTING`, `IDLE`, `LISTENING`, `PROCESSING`, `SPEAKING`, `SHUTDOWN`), and handles Event Bus dispatching.
* **`/backend/modules/`:** The home of specialized capability engines. Each subdirectory represents a standalone, isolated package with its own API contract, meaning a developer can refactor a module's internal code without affecting the Orchestrator.

### Configuration (`/config/`)
* Holds structured, editable JSON or YAML files representing:
  * Active feature flag settings
  * User preferences (e.g., Speak output: True/False)
  * Voice speed, volume, and wake-word sensitivities
  * Directory paths allowed for PC control operations

### Testing (`/testing/`)
* Completely mirrors the production layout of `/backend/modules/` inside `/testing/unit/` for direct file mapping.
* Runs independently via `pytest` to prevent packaging bloat inside the production app.
