# Naira-OS

A lightweight, modular personal desktop AI assistant designed for low-resource hardware (Intel i3 6th Gen, 4 GB RAM). Built on a Micro-Kernel + 6-Layer Clean Architecture with `asyncio`-based concurrency.

**Current Phase:** Phase 4.1 Completed — Transitioning to Phase 4.2 (Android Remote App & Security Vault)

---

## Key Features

- **Secure Remote Bridge (Ngrok + FCM + Zero-Trust):** Public out-of-network remote communication via Ngrok WebSockets ([`/ws/remote`](file:///c:/Users/user/Desktop/Project-AIF-main/docs/08_API_Design.md)), FCM high-priority silent background wake-up pings, thread-safe offline action queueing, HMAC-SHA256 payload signing, nonce replay protection, and dynamic risk scoring (`score > 80` enforcing biometric challenge).
- **Master Fast Command Router (FCR Phase 2):** High-speed deterministic phrase matching engine executing system actions with sub-5ms latency.
- **Autonomous Coding Agent & 24 Skill Packs:** Multi-language project analysis and automated code generation across Python, C, C++, Java, JS, TS, React, Next.js, FastAPI, Docker, SQL, Git, and more.
- **Proactive Health Watchdog:** Background system vitals monitoring with warm-up CPU sampling and non-blocking synthesized voice alerts.
- **Reliable LLM Response Caching:** In-memory LRU cache with strict tool-call bypassing to eliminate destructive action replay risks.

---

## Architecture

The system follows a **Micro-Kernel pattern** combined with **Clean Architecture**:

- **Core Kernel** — Orchestrator, Security Manager, Configuration Manager, Logger (~50MB resident)
- **Plug-In Modules** — Voice, Vision, Browser, Avatar, Remote Bridge, etc. loaded lazily only when activated

Code dependencies flow strictly downward across six layers:

```
Presentation → Application → AI Core → Service → Infrastructure → OS
```

Communication uses a **Mediator pattern** (Orchestrator routes requests) and an **Event Bus** for async pub/sub notifications.

---

## Python Version

Requires **Python 3.12+** (uses `type` alias syntax, `StrEnum`, and other 3.12 features).

---

## Setup

```bash
# Clone the repository
git clone https://github.com/your-org/naira-os.git
cd naira-os

# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
source .venv/bin/activate  # Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your NAIRA_GEMINI_API_KEY and REMOTE_BRIDGE_MASTER_KEY

# Run
python main.py
```

---

## Project Structure

```
AI_Assistant/
├── main.py                  # Entry point & asyncio event loop bootstrap
├── run_cli.py               # Interactive CLI terminal loop runner
├── backend/                 # Core Python package
│   ├── orchestrator.py      # FSM, Event Bus, module registry
│   ├── types.py             # Shared dataclasses, enums, protocols
│   ├── exceptions.py        # Exception hierarchy
│   └── modules/
│       ├── remote_bridge/   # Ngrok WS Router, FCM Manager, Zero-Trust Security Engine
│       ├── settings/        # Config, env, and feature flag loading
│       └── utils/           # DI container, logging utilities
├── config/                  # JSON/YAML configuration files
├── docs/                    # Architecture, design, and specification docs
├── logs/                    # Rotating log files
└── testing/                 # Unit and integration tests
```

---

## Roadmap

| Phase | Status | Focus |
|-------|--------|-------|
| **0.5 – 3.0** | Completed | Core Architecture, FCR, SQLite Memory, CLI & WS Gateways |
| **4.0** | Completed | Proactive Watchdog & LLM Caching Reliability |
| **4.1** | **Completed** | Secure Remote Bridge Backend (Ngrok + FCM + Zero-Trust Security) |
| **4.2** | **Active / Upcoming** | Android Remote App & Hardware-Backed Security Vault |
| **5.0 – 5.1** | Completed | Coding Agent Subsystem, 24 Skill Packs, Grand Unified Patch |
| **6.0** | Planned | Production Hardening, 3D Anime Avatar IPC, Extension Ecosystem |

---

## License

Distributed under the **MIT License**. See [LICENSE](LICENSE) for details.

---

## Contributing

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/amazing-feature`).
3. Commit your changes (`git commit -m 'Add amazing feature'`).
4. Push to the branch (`git push origin feature/amazing-feature`).
5. Open a Pull Request.

All contributions must follow the coding standards and system contracts defined in `docs/`.
