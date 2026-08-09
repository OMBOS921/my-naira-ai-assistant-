# Project-AIF-main / Naira-OS — Full Technical Explanation

> **Note:** The repository folder is referred to as `Project-AIF-main`, but all analysis reports identify the product as **Naira-OS**. The explanation below combines the findings from the 9 specialized agents.

---

## 1. What Is Naira-OS?

Naira-OS is a **modular, event-driven AI assistant platform**. It provides:

- A **FastAPI backend** with WebSocket/REST endpoints
- A **React frontend** with an "API Vault" onboarding screen
- A **multi-stage security → decision → execution pipeline**
- A **runtime tool-execution engine**
- **Code generation, planning, and direct LLM chat**
- **Modular backend architecture** with 24 modules
- An **EventBus** for inter-module communication
- A **MemoryManager** for conversation/artifact persistence
- Planned **PC/OS control** capabilities

It is essentially a sophisticated AI agent framework, not just a chatbot.

---

## 2. Critical Security Warning (Read First)

🚨 **The file `firebase_credentials.json` contains a live Google Cloud service account private key and is committed to the repository.**

This is a **critical credential leak**. Anyone with access to the repo can impersonate the service account and access Firebase services for the `naira-os` project.

### Immediate actions required:

1. **Rotate the key** in Google Cloud Console.
2. **Remove the file from Git history** — deleting it in a new commit is not enough.
3. **Add it to `.gitignore`**.
4. **Check Firebase audit logs** for unauthorized access.
5. **Never commit secrets** — use env vars or a secret manager.

---

## 3. High-Level Architecture

```
Client (WebSocket / REST / CLI / Android Bridge)
        │
        ▼
┌─────────────────────────────────────┐
│  main.py  (FastAPI + lifespan)      │
│  • Load .env                        │
│  • Load API keys from vault         │
│  • Create Orchestrator              │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Orchestrator (FSM)                 │
│  • BOOTING → RUNNING → SHUTTING_DOWN│
│  • Module lifecycle management      │
│  • EventBus injection               │
│  • Health verification              │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  RuntimeManager                     │
│  • Tool execution loop              │
│  • Stage-gated pipeline             │
└──────┬──────────────┬───────────────┘
       │              │
       ▼              ▼
┌─────────────┐  ┌──────────────────────┐
│ Stage 0     │  │ Stage 1              │
│ Security    │  │ Decision             │
└──────┬──────┘  └──────────┬───────────┘
       │                    │
       └────────┬───────────┘
                ▼
┌──────────────────────────────────────┐
│ Stage 2: Execution Pathways          │
│                                      │
│ • FCR (Fast Command Router)          │
│ • PlanningAgent                      │
│ • CodingAgentManager                 │
│ • LLM Adapters (Gemini/Groq/Local)   │
└──────────────────────────────────────┘
```

---

## 4. Project Structure

```
naira-os/
│
├── main.py                          # FastAPI entry point
├── .env                             # Environment variables
├── firebase_credentials.json        # ⚠️ EXPOSED — must remove
├── backend/
│   ├── orchestrator.py              # Central FSM
│   ├── runtime/
│   │   └── _runtime_manager.py      # Tool execution loop
│   ├── modules/                     # 24 modules
│   │   ├── decision/                # Intent routing + scoring
│   │   ├── security/                # Security manager (Stage 0)
│   │   ├── pc_control/              # OS control (planned)
│   │   ├── vision/                  # Screen capture
│   │   ├── syntax_master/           # ⚠️ Disconnected from production
│   │   └── ...
│   └── services/
│
├── memory/
│   └── user_vault.json              # Runtime API key vault
│
├── testing/
│   ├── unit/
│   └── integration/
│       └── test_boot_sequence.py
│
├── config/
│   ├── features.yaml
│   ├── security_policy.yaml
│   ├── apps_aliases.yaml
│   └── llm_providers.yaml
│
├── frontend/                        # React app
└── docs/
```

---

## 5. Core Boot Sequence

The system is initialized in `main.py` via FastAPI's **lifespan manager**:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dotenv()
    load_groq_api_key_from_vault(...)

    orchestrator = Orchestrator()
    await orchestrator.boot()      # <-- failing in tests
    yield
    await orchestrator.shutdown()
```

### Boot order (dependency-first):

1. `EventBus`
2. `ConfigManager`
3. `SecurityManager`
4. `DecisionManager`
5. `RuntimeManager`
6. `FCR` (Fast Command Router)
7. `PlanningAgent`
8. `CodingAgentManager`
9. `LLM Adapters`
10. `MemoryManager`
11. `PC Control`
12. `Vision Module`

Every module:

- Gets the **EventBus** injected
- Implements `initialize()`, `start()`, `stop()`, `health_check()`
- Publishes lifecycle events like `module.initialized`

Orchestrator verifies **health of all modules** after boot.

---

## 6. Request Handling Pipeline

When a user request arrives:

### Stage 0 — Security

`SecurityManager` validates:

- Input sanitization
- Authorization
- Rate limiting
- Policy enforcement

### Stage 1 — Decision

`DecisionManager` classifies intent and scores routes:

```python
score_route("coding")    = 0.95
score_route("planning")  = 0.30
score_route("fcr")       = 0.05
```

The highest-scoring route is chosen.

### Stage 2 — Execution

The RuntimeManager dispatches to:

| Route | Handled By |
|-------|-----------|
| Fast command | `FCR` — instant pattern-based command router |
| Complex task | `PlanningAgent` — decomposes into steps |
| Code task | `CodingAgentManager` — generates/executes code using LLM |
| Direct chat | `LLM Adapters` — Gemini/Groq/Local completion |

> **Important:** The `syntax_master` / AST pipeline has been **disconnected**. All code tasks now go directly to the main LLM via `CodingAgentManager`. This simplifies the flow but increases trust in the LLM output.

---

## 7. Key Modules and Features

### 7.1 EventBus
The central nervous system. All modules communicate via async pub/sub:

```python
await self.event_bus.publish("tool.executed", data)
```

Events include:

- `module.initialized`
- `module.health_check`
- `request.received`
- `security.violation`
- `decision.made`
- `tool.executed`
- `llm.stream_chunk`
- `shutdown.initiated`

### 7.2 SecurityManager
Enforces trust boundaries:

```
PUBLIC (client)     →  INTERNAL (runtime)     →  PRIVILEGED (system)
```

It validates every cross-boundary call.

### 7.3 DecisionManager
Scores and selects the best execution route for each request.

### 7.4 RuntimeManager
The core execution engine that orchestrates the staged pipeline.

### 7.5 CodingAgentManager
Handles code generation tasks:

- Decomposes tasks into sub-tasks
- Uses LLMs to generate code
- Writes artifacts to workspace
- Communicates results via EventBus

### 7.6 LLM Adapters
Supports multiple LLM providers:

- Gemini (primary)
- Groq (fallback)
- Local LLM (optional)

Keys are loaded from `.env` and `memory/user_vault.json`.

### 7.7 MemoryManager
Stores conversation context and generated artifacts.

### 7.8 PC Control (Planned)
Extends OS-level control:

- Open applications
- Navigate URLs
- Desktop automation
- Cross-platform (Windows/macOS/Linux)

### 7.9 Vision Module
Screen capture and visual understanding. Currently has one failing unit test.

### 7.10 API Vault (Frontend)
A mandatory gatekeeper screen in the React app. Users must provide LLM API keys before they can use the system. Without a valid vault, users cannot proceed to the dashboard.

---

## 8. Inter-Module Communication

The communication architecture uses **several patterns**:

| Pattern | Used For |
|---------|----------|
| Pub/Sub | Inter-module events via EventBus |
| Dependency injection | Modules receive EventBus and Config |
| Stage-gated pipeline | Security → Decision → Execution |
| Strategy pattern | Executors (FCR/Planning/Coding/LLM) |
| Observer pattern | ConfigManager watchers |
| Repository pattern | MemoryManager persistence |
| Gatekeeper pattern | SecurityManager at boundaries |

### Configuration communication

```python
# Modules subscribe to config changes
await self.config.watch("features.coding_agent_enabled", self._on_feature_toggle)
```

Config files:

- `features.yaml` — feature flags
- `security_policy.yaml` — security rules
- `apps_aliases.yaml` — app aliases for PC control
- `llm_providers.yaml` — model/endpoint settings
- `skill_packs/` — coding agent skill definitions

---

## 9. Testing Status

### Regression baseline

| Metric | Value |
|--------|-------|
| Total tests | 2548 |
| Passed | 2535 (99.49%) |
| Failed | 13 (0.51%) |
| Duration | 284.4s (~4.7 min) |

### Failure breakdown

| Test File | Failures |
|-----------|----------|
| `testing/integration/test_boot_sequence.py` | 12 |
| `testing/unit/modules/vision/test_vision_module.py` | 1 |

### Likely causes

1. **Boot sequence failures** — likely shared root cause:
   - Module initialization order regression
   - EventBus not properly injected
   - Health check protocol mismatch
   - Resource leaks between tests
   - Asynchronous timing issues

2. **Vision module failure** — isolated unit test:
   - Mock/behavior expectation mismatch
   - Possibly platform-dependent screen capture issue

### Recommended test fixes

- Add a central `conftest.py`
- Mock external services (LLMs, filesystem, hardware)
- Use function-scoped fixtures to prevent state leakage
- Configure `pytest-asyncio` with `asyncio_mode = "auto"`
- Add timeouts and retries for async health checks
- Split overloaded integration tests into smaller focused tests
- Skip platform-dependent tests on headless CI

---

## 10. Performance and Code Quality Observations

### High-impact issues

| Issue | Impact | Fix |
|-------|--------|-----|
| Sync file I/O in `load_groq_api_key_from_vault` | Blocks event loop on startup | Cache with `functools.lru_cache` or async I/O |
| `load_dotenv(override=True)` on every import | Repeated `.env` parsing | Guard with a module-level flag |
| `syntax_master` dead code retained on disk | Wasted memory/image size | Move to archive or feature-flag it |
| 12 boot-sequence test failures | Possibly resource leaks | Add `tracemalloc` and isolated fixtures |
| Missing `requirements.txt` | No dependency pinning | Create one with pinned versions |

### Low-hanging fixes

- Remove unused imports (`base64`, `io`, `threading`, `time`)
- Use `os.environ.pop("GROQ_API_KEY", None)` instead of setting empty string
- Parallelize independent module initialization with `asyncio.gather`
- Validate environment variables at startup

---

## 11. Recommended Roadmap

1. 🔴 **Rotate and remove exposed Firebase credentials** — do this first.
2. 🔴 **Fix boot sequence tests** — the 12 failures point to a broken core lifecycle.
3. 🟠 **Improve test isolation** — add conftest fixtures and mocks.
4. 🟠 **Implement proper secrets management** — env vars or secret manager.
5. 🟡 **Remove or disable dead code** (`syntax_master`).
6. 🟡 **Add dependency pinning** (`requirements.txt` / `pyproject.toml`).
7. 🟢 **Optimize startup** — cache vault reads, parallelize module boot.

---

## 12. Summary

Naira-OS is a **well-structured, modular AI assistant platform** with a clear separation of concerns:

- **FastAPI** handles ingress
- **Orchestrator** manages module lifecycle
- **RuntimeManager** routes requests through security → decision → execution
- **EventBus** keeps modules loosely coupled
- **24 backend modules** provide capabilities like coding, planning, vision, memory, and PC control
- **React frontend** enforces API key onboarding

The architecture is solid, but the project is currently **not fully healthy**:

- Critical security leak
- Broken boot sequence tests
- Some dead code
- Performance improvements available

Fixing the security issue and stabilizing the boot sequence should be the **immediate priorities**. Once those are resolved, the platform is in a strong position to evolve into a full AI operating system.