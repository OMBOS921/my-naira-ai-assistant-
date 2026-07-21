# Naira-OS

A lightweight, modular personal desktop AI assistant designed for low-resource hardware (Intel i3 6th Gen, 4 GB RAM). Built on a Micro-Kernel + 6-Layer Clean Architecture with `asyncio`-based concurrency.

**Current Phase:** 0.5 — Architectural Blueprint & Specifications

## Architecture

The system follows a **Micro-Kernel pattern** combined with **Clean Architecture**:

- **Core Kernel** — Orchestrator, Security Manager, Configuration Manager, Logger (~50MB resident)
- **Plug-In Modules** — Voice, Vision, Browser, Avatar, etc. loaded lazily only when activated

Code dependencies flow strictly downward across six layers:

```
Presentation → Application → AI Core → Service → Infrastructure → OS
```

Communication uses a **Mediator pattern** (Orchestrator routes requests) and an **Event Bus** for async pub/sub notifications.

## Python Version

Requires **Python 3.12+** (uses `type` alias syntax, `StrEnum`, and other 3.12 features).

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
# Edit .env and add your NAIRA_GEMINI_API_KEY

# Run
python main.py
```

## Project Structure

```
AI_Assistant/
├── main.py                  # Entry point & asyncio event loop bootstrap
├── backend/                 # Core Python package
│   ├── orchestrator.py      # FSM, Event Bus, module registry
│   ├── types.py             # Shared dataclasses, enums, protocols
│   ├── exceptions.py        # Exception hierarchy
│   └── modules/
│       ├── settings/        # Config, env, and feature flag loading
│       └── utils/           # DI container, logging utilities
├── config/                  # JSON/YAML configuration files
├── docs/                    # Architecture, design, and specification docs
├── logs/                    # Rotating log files
└── testing/                 # Unit and integration tests
```

## Roadmap

| Phase | Focus |
|-------|-------|
| **0.5** (current) | Architectural blueprint, module contracts, coding standards |
| 1 | Core foundation: event loop, config, logging, CLI |
| 2 | Local memory & context pipeline (SQLite, token management) |
| 3 | Voice I/O (STT/TTS), interactive CLI |
| 4 | Sandboxed PC control & file automation |
| 5 | Multimodal screen vision (screenshots, OCR) |
| 6 | Production hardening, 3D avatar, plugin system |

## License

Distributed under the **MIT License**. See [LICENSE](LICENSE) for details.

## Contributing

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/amazing-feature`).
3. Commit your changes (`git commit -m 'Add amazing feature'`).
4. Push to the branch (`git push origin feature/amazing-feature`).
5. Open a Pull Request.

All contributions must follow the coding standards and system contracts defined in `docs/`.
