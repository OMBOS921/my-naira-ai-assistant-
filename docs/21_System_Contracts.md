# 21. System Contracts

**Constitutional Document — Naira-OS Personal Desktop AI Assistant**

This document is the single source of truth for all engineering decisions. Every future module, refactoring, pull request, and architectural discussion defers to the rules defined here. In case of conflict between this document and any other document in `docs/`, this document prevails.

---

## 1. Purpose of System Contracts

1.1. **Alignment:** Every developer must be able to predict how any new module behaves, how it is wired, and how it is tested without reading every existing module.

1.2. **Longevity:** The rules in this document must remain valid across major versions. Changes to this document require a MAJOR version bump.

1.3. **Automation:** Rules marked with `[LINT]` are candidates for automated enforcement via linters, import checkers, or CI gates once the module structure stabilises.

1.4. **Scope:** This document covers architecture, module design, coding standards, testing, dependency management, lifecycle, and security. It does not cover product requirements, roadmaps, or UI mockups (those belong in `01_Project_Vision.md`, `13_Roadmap.md`, and `08_API_Design.md` respectively).

---

## 2. Global Architecture Rules

2.1. **Architectural Style:** The system uses a **Micro-Kernel (Core-Plug) pattern** combined with **6-Layer Clean Architecture** as defined in `04_Architecture.md`.

2.2. **Core Kernel:** The following components are always running (the "micro-kernel"):
    - Orchestrator (`backend/orchestrator.py`)
    - Security Manager (`backend/modules/security/`)
    - Configuration Manager (`backend/modules/settings/`)
    - Logger (`backend/modules/utils/logger/`)

2.3. **Downward-Only Dependency Rule:** Code dependencies flow strictly downward through the six layers. No lower layer (higher number) may import or depend on a higher layer (lower number). This rule is absolute.

2.4. **No Circular Imports:** The dependency graph of all modules must be a directed acyclic graph (DAG). Any circular import is a design error and must be resolved by introducing a Port (see §6).

2.5. **Mediator Pattern:** The Orchestrator is the sole mediator for all request-response flows. Modules never call each other directly. Inter-module communication passes through the Orchestrator.

2.6. **Event Bus:** Asynchronous pub-sub events use a single `EventBus` instance owned by the Orchestrator. No other component creates, owns, or replaces the Event Bus.

2.7. **Lazy Loading:** Heavy modules (Voice, Vision, Browser, 3D Avatar) are imported and instantiated only when first requested. The Feature Flag Manager (in `backend/modules/settings/`) controls which modules are pre-loaded vs lazy-loaded.

2.8. **Hardware Target:** All code must run on Intel i3 6th Gen with 4 GB RAM. This constraint is non-negotiable. Any feature that exceeds this budget must be gated behind a feature flag defaulting to `false`.

---

## 3. Layer Contracts

Each layer has a strict responsibility boundary. Code placed in the wrong layer is a design defect.

### Layer 1 — Presentation
| Aspect | Rule |
|---|---|
| Role | Manage input/output channels (CLI, WebSocket, System Tray) |
| Constraint | Zero business logic. Zero AI prompt processing. Zero direct calls to AI Core, Service, Infrastructure, or OS layers. |
| Allowed imports | Cross-cutting, Layer 2 |
| May own | Input readers, output writers, WebSocket handlers, avatar IPC socket |
| Must NOT own | Any LLM call, any database query, any OS automation |
| Example modules | `avatar/` (Phase 6), CLI reader (in main.py or a standalone module) |

### Layer 2 — Application
| Aspect | Rule |
|---|---|
| Role | Manage features, sessions, capabilities, and feature toggles |
| Constraint | Must not import Layer 4, 5, or 6 directly |
| Allowed imports | Cross-cutting, Layer 3 (via Orchestrator for routing) |
| May own | Capability registry, session tokens, feature flags, user preferences, plugin lifecycle |
| Example modules | `capability/`, `session/`, `plugin/`, `settings/`, `permissions/`, `telemetry/` (Phase 6), `update/` (Phase 6) |

### Layer 3 — AI Core
| Aspect | Rule |
|---|---|
| Role | Cognitive brain: reasoning, history, intent orchestration |
| Constraint | Must not import Layer 4+ directly. Must use Ports (see §6) for all cross-layer service access. |
| Allowed imports | Cross-cutting, Layer 4 via Ports only |
| May own | LLM provider adapters, prompt templates, context window, conversation history |
| Example modules | `orchestrator.py`, `llm/`, `prompt/`, `context/` |

### Layer 4 — Service
| Aspect | Rule |
|---|---|
| Role | Wrap heavy execution engines into standard interfaces |
| Constraint | Must not import Layer 1, 2, or 3 |
| Allowed imports | Cross-cutting, Layer 5, Layer 6 |
| May own | TTS/STT wrappers, OCR, screen capture, browser automation, file I/O adapters |
| Example modules | `voice/`, `vision/`, `browser/`, `file_manager/` |

### Layer 5 — Infrastructure
| Aspect | Rule |
|---|---|
| Role | Concrete adapters for databases, file storage, and system logs |
| Constraint | Must not import Layer 1-4 |
| Allowed imports | Cross-cutting, Layer 6 |
| May own | SQLite client, vector index, file logger, configuration persistence |
| Example modules | `memory/` |

### Layer 6 — Operating System
| Aspect | Rule |
|---|---|
| Role | Direct interface with Windows OS and physical devices |
| Constraint | Must not import any backend module. Only cross-cutting. |
| Allowed imports | `utils/` only (not `security/` — security rules are enforced by Layer 3/4 calling the permission gatekeeper) |
| May own | PyAutoGUI calls, subprocess wrappers, audio device access, process manager |
| Example modules | `pc_control/` |

### Cross-Cutting (no layer)
| Module | Scope | Restriction |
|---|---|---|
| `security/` | Available to all layers | Must NOT import any `backend/` module. Stdlib + utils only. |
| `utils/` | Available to all layers | Must NOT import any `backend/` module. Stdlib + pinned third-party packages only. |

---

## 4. Module Contracts

Every module in `backend/modules/{name}/` must conform to this interface:

```
Module
├── __init__.py          # Exports exactly one public class: {PascalCase}Manager
├── ports/               # (optional) Port definitions if this module defines abstractions
│   └── *Port.py
├── adapters/            # (optional) Adapter implementations if this module provides concretions
│   └── *Adapter.py
└── {name}_module.py     # Private implementation
```

4.1. **Registration:** Each module exposes a single public class (e.g., `LLMManager`, `ContextManager`). The class is constructable with all dependencies passed explicitly.

4.2. **ModuleInterface Protocol:** Every module class should conceptually conform to:

```
- __init__(self, *, config, logger, ...)          # positional args forbidden for public API
- async_init(self) -> None                        # optional: heavy async setup
- async_shutdown(self) -> None                    # optional: cleanup
- degrade(self) -> None                           # optional: release heavyweight resources on error
```

4.3. **No Module-Level State:** A module must not define module-level mutable objects. All state lives in the instance.

4.4. **No Global Registry:** A module must not self-register into a global registry. Registration happens explicitly at boot time via the Orchestrator.

4.5. **Graceful Degradation:** Every module must be designed to fail at construction or `async_init()` without crashing the Orchestrator. The system continues in degraded mode.

4.6. `[LINT]` **Single Export Rule:** `__init__.py` must export exactly one public class. Internal classes and functions are private (prefixed with `_`).

---

## 5. Dependency Injection Rules

5.1. **Constructor Injection Only:** Every module receives its dependencies via keyword-only arguments to `__init__`. No positional arguments for the public constructor.

5.2. **No Service Locator:** The Orchestrator does not expose a `get_service()` method. The Capability Manager is for routing, not for dependency lookup.

5.3. **No Global State:** No module may read from or write to a global variable (including module-level mutables, `os.environ`, or `sys.modules` manipulation) except:
    - The Logger (which is initialised before any module is constructed).
    - The Configuration Manager (which produces an immutable `AppConfig` snapshot).

5.4. **Wiring Location:** All wiring (constructing modules with their dependencies) happens in one place: `main.py` or a dedicated `bootstrapper.py` called by `main.py`.

5.5. `[LINT]` **Orchestrator Not Importable:** `from backend.orchestrator import ...` is forbidden in any module. The Orchestrator injects itself into modules that need it via constructor injection.

---

## 6. Interface (Port/Adapter) Rules

6.1. **When to Use:** When Layer N needs a service from Layer N+2 or deeper, a Port must be defined. Direct imports that skip a layer are forbidden.

6.2. **Port Definition:**
    - The Port lives in `backend/modules/{consumer}/ports/{service}_port.py`.
    - It is an abstract class using `abc.ABC` and `@abstractmethod` (or a `typing.Protocol` for structural typing).
    - It uses only types that the consumer layer owns or types from cross-cutting modules.

6.3. **Adapter Implementation:**
    - The Adapter lives in `backend/modules/{provider}/adapters/{name}_adapter.py`.
    - It inherits from the Port it implements.
    - It may import from layers below itself but must not import the consumer's non-port code.

6.4. **Wiring:**
    - The Adapter is instantiated by the bootstrapper and passed to the consumer's constructor.
    - The consumer never imports the adapter. It only imports its own Port.
    - No DI framework. Manual wiring in `main.py` or `bootstrapper.py`.

6.5. **Ports Are Public API:** A Port's signature is a compatibility contract. Changing it requires a MAJOR version bump.

6.6. **Required Ports (established at architecture baseline):**

| Consumer | Port | Adapter(s) |
|---|---|---|
| `context/` | `MemoryPort` | `memory.SQLiteMemoryAdapter` |
| `llm/` | `LLMPort` | `llm.providers.GeminiAPIAdapter`, `OllamaAdapter`, `DeepSeekAdapter` |
| `memory/` | `VectorIndexPort` | `memory.JSONVectorIndexAdapter` |
| `plugin/` (Phase 6) | `PluginPort` | (external plugins) |

---

## 7. Configuration Rules

7.1. **Configuration Sources (priority order: low → high):**

```
1. config/defaults.yaml          # Ship with the application. Never modified by runtime.
2. config/{environment}.yaml     # Environment-specific overrides (e.g., config/production.yaml)
3. config/user.yaml              # User edits via settings UI. Created on first save.
4. .env                          # Secrets and machine-specific values. Never committed.
5. Runtime overrides             # CLI flags (-v, --config-path) and programmatic set() calls.
```

Higher-numbered sources override lower-numbered sources. Scalar values are replaced; dict values are deep-merged.

7.2. **Secrets:** All secrets (API keys, tokens, passwords) live exclusively in `.env`. See `09_Security.md` §1.

7.3. **Schema Validation:** Every config file must have a corresponding JSON Schema in `config/schemas/{name}.schema.json`. Boot fails if the file violates its schema.

7.4. **Runtime Access:** Modules access configuration via a frozen `AppConfig` dataclass tree, injected at construction. Modules must not call `json.load()` or `yaml.safe_load()` directly.

7.5. **Immutable at Runtime:** Config values loaded at boot are immutable for the lifetime of the process. Runtime overrides (priority 5) are persisted to `config/user.yaml` and take effect on next boot.

7.6. **Environment Variable Names:** All env vars used by the application must be prefixed with `NAIRA_` (e.g., `NAIRA_GEMINI_API_KEY`). Backward compatibility with unprefixed names is permitted only for well-known conventions (e.g., `GEMINI_API_KEY`).

---

## 8. Logging Standards

8.1. **Logger Instance:** Every module receives a module-scoped logger instance via dependency injection. The logger is a standard `logging.Logger` with a structured format.

8.2. **Log Format:**
```
[TIMESTAMP] [LEVEL] [MODULE] [REQUEST_ID?] [MESSAGE] [KEY=VALUE ...]
```
Example:
```
[2026-07-12 14:30:01.123] [INFO] [LLMManager] [req_a1b2] Provider=Gemini Tokens=142 Duration=1.23s
```

8.3. **Log Levels:**
    - `ERROR`: Unrecoverable errors within a module. System continues in degraded mode.
    - `WARNING`: Recoverable issues, config fallbacks, slow operations.
    - `INFO`: Boot sequence, module state transitions, significant lifecycle events. Default level.
    - `DEBUG`: Detailed diagnostic information. Not logged in production unless explicitly enabled.
    - `TRACE` (conceptual): Reserved for future per-module verbose logging.

8.4. **No Secrets in Logs:** Log messages must never contain API keys, tokens, passwords, or personal identifiable information. `[LINT]` scanners must flag potential secrets before merge.

8.5. **File Rotation:** `logs/naira_YYYY-MM-DD.log`, max 10 MB per file, keep 30 days. Console output is stdout at INFO level.

8.6. **Structured Audit Log:**
    Security-critical events (credential loading, file modification, terminal execution, permission granting) additionally write to a structured audit log with format:
    ```
    [TIMESTAMP] [MODULE] [ACTION] [SECURITY_STATUS: GRANTED/BLOCKED]
    ```

---

## 9. Exception Handling Standards

9.1. **Exception Hierarchy:** All application exceptions inherit from a base `NairaError(Exception)` defined in `backend/exceptions.py`.

9.2. **Base Hierarchy:**
```
NairaError
├── ConfigurationError      # Config validation failure
├── ModuleError             # Base for module-level errors
│   ├── ModuleLoadError     # Module construction or async_init failure
│   ├── ModuleTimeoutError  # Module operation exceeded deadline
│   └── ModuleDegradedError # Module is in degraded state
├── SecurityError           # Base for security violations
│   ├── InputRejectedError  # Payload failed validation
│   ├── PermissionDeniedError # User denied or no session
│   └── AuditLogError       # Audit log write failure
├── LLMError                # Base for LLM provider errors
│   ├── ProviderTimeoutError
│   ├── ProviderRateLimitError
│   └── ProviderAuthError
├── MemoryError             # Database or cache errors
│   ├── IntegrityError      # SQLite constraint violation
│   └── NotFoundError       # Key/record not found
└── ToolExecutionError      # Error during tool/module execution
    ├── ToolTimeoutError
    └── ToolRejectedError   # Permission gatekeeper rejection
```

9.3. **Catching Policy:**
    - The Orchestrator is the primary exception handler for all request-processing paths.
    - Modules must not catch exceptions they cannot handle meaningfully.
    - The Orchestrator catches `NairaError` subtypes for structured error responses.
    - Non-`NairaError` exceptions are considered bugs. They propagate to `sys.excepthook`, which logs a full traceback and sends an error response to the user.

9.4. **No Bare Excepts:** A bare `except:` is forbidden. Every `except` clause must specify at least one exception type. `except Exception` is permitted only at the Orchestrator's top-level request handler.

9.5. **Context in Exceptions:** Every `NairaError` must carry a `context` dict with relevant debugging information (module name, request ID, operation, duration).

---

## 10. Async Programming Rules

10.1. **Event Loop:** `asyncio.run(main())` is the single entry point. No module creates or replaces the event loop.

10.2. **No Blocking Calls:** `time.sleep()`, `socket.recv()` (without async wrapper), `requests.get()`, and `subprocess.run()` (synchronous) are forbidden in modules. Use `asyncio.sleep()`, `asyncio.open_connection()`, `aiohttp`, and `asyncio.create_subprocess_exec()` instead.

10.3. **CPU-Bound Work:** Long-running CPU-bound operations (Whisper inference, OCR, heavy computation) must be offloaded to `asyncio.to_thread()` or `concurrent.futures.ProcessPoolExecutor`. The Sequential Queue (see `04_Architecture.md` §4) applies: only one CPU-bound task runs at a time.

10.4. **Task Creation:** `asyncio.create_task()` is reserved for the Orchestrator and the Event Bus. Modules must not create tasks arbitrarily. If a module needs background work, it must register a coroutine factory with the Orchestrator, which manages the task lifecycle.

10.5. **Cancellation:** All async operations must handle `asyncio.CancelledError` gracefully (clean up resources, log, then re-raise or complete shutdown).

10.6. **Timeouts:** Every async operation that involves I/O or external service calls must have a timeout via `asyncio.wait_for()` or `asyncio.timeout()` (Python 3.12+). Default timeouts are defined in `19_Request_Lifecycle.md` §5.

10.7. **No Fire-and-Forget:** A coroutine that is created (via `create_task()` or `gather()`) must either be awaited, stored in a managed collection, or explicitly cancelled. Orphaned tasks (not referenced, not awaited) are forbidden.

---

## 11. Resource Management Rules

11.1. **Garbage Collection:** After unloading a heavyweight module (Vision, Voice, Browser), the Orchestrator must call `gc.collect()`. This is the only place `gc.collect()` is called — individual modules must not invoke it.

11.2. **File Handles:** Every file handle opened by a module must be closed within the same method or managed via a context manager (`with` statement). Modules must not hold open file handles across request boundaries unless they are managed by the Module's `async_shutdown()`.

11.3. **Database Connections:** The Memory Manager (`backend/modules/memory/`) owns the single SQLite connection. No other module opens a database connection. The connection is opened during `async_init()` and closed during `async_shutdown()`.

11.4. **Subprocesses:** Every subprocess created by `pc_control/` or `file_manager/` must be tracked and terminated during shutdown. The process manager in `pc_control/` maintains a registry of active PIDs.

11.5. **Large Objects:** Modules that hold large in-memory objects (Whisper model weights, OpenCV buffers, Playwright browser instance) must implement `degrade()` to release these objects eagerly when the module enters degraded state.

11.6. **Memory Budget (Target):**
    - Core kernel (Orchestrator + Security + Config + Logger): ~50 MB
    - Active medium module (Context, Prompt, LLM provider): ~50-100 MB
    - Heavy module loaded (Voice STT, Vision, Browser): ~200-400 MB
    - System must function with at most 2 GB allocated to the Python process (leaving 2 GB for OS).

---

## 12. Startup Contracts

12.1. **Startup Order:** The 12-step boot sequence defined in `18_Boot_Sequence.md` §2 is mandatory. Steps may not be reordered without a MAJOR version discussion.

12.2. **Failure Policy:**
    - Environment validation failure: fatal (exit).
    - Configuration schema violation: fatal (exit).
    - Logger init failure: fall back to console, continue.
    - Security init failure: fatal (exit) — cannot boot without security.
    - Module construction failure: mark degraded, continue.
    - Module `async_init()` timeout: mark degraded, continue.
    - CLI init failure: fatal (exit) — no user I/O possible.
    - WebSocket init failure: log warning, continue with CLI only.

12.3. **Boot Readiness:** The Orchestrator must not transition to `IDLE` until all steps in §2 of `18_Boot_Sequence.md` have completed or been marked degraded.

12.4. **Boot Log:** On transition to `IDLE`, the Orchestrator logs `[BOOT] System ready in X.XXs. Modules: N active, M lazy, D degraded.`

12.5. **Lazy-Load Contract:** A lazy module loaded on demand must complete `async_init()` within `config.modules.lazy_load_timeout` (default 30 s). If it exceeds this, it is marked degraded for the remainder of the session.

---

## 13. Shutdown Contracts

13.1. **Shutdown Order:** The 7-step shutdown sequence defined in `18_Boot_Sequence.md` §4 is mandatory. Steps may not be reordered.

13.2. **Grace Periods:**
    - Presentation shutdown: 3 s
    - Per-module `async_shutdown()`: 5 s
    - Session persist (SQLite write): 2 s
    - Event Bus drain: 100 ms

13.3. **Forced Termination:** If a module's `async_shutdown()` exceeds its grace period, the Orchestrator cancels the task and proceeds to the next step. The module is logged as `[SHUTDOWN] Module {name} shutdown timed out.`

13.4. **Double Shutdown:** Calling shutdown twice on the same module must be safe (idempotent). The module must track its own shutdown state.

13.5. **Crash Recovery:** The system does not auto-restart after a crash. On next boot:
    - If SQLite WAL file indicates an unclean shutdown, run `PRAGMA integrity_check`.
    - Corrupt databases are renamed `{name}.corrupt` and a fresh database is created.
    - Logs from the previous session are preserved in `logs/`.

---

## 14. Event Bus Contracts

14.1. **Ownership:** The `EventBus` is created during boot Step 5 and owned by the Orchestrator as a private attribute.

14.2. **Event Schema:**
```
Event:
  type: str             # Dot-separated, e.g., "system.memory_warning"
  source: str           # Registered module name
  data: dict[str, Any]  # Payload
  priority: str         # "high" | "normal" | "low"
  timestamp: float      # Unix time
```

14.3. **System Event Channels (pre-registered at boot):**
    - `system.shutdown` — Published by Orchestrator or OS monitor
    - `system.memory_warning` — Published by Telemetry Manager
    - `system.error` — Published by any module on unrecoverable error
    - `permission.granted` — Published by Security Manager
    - `permission.revoked` — Published by Security Manager
    - `module.loaded` — Published by Orchestrator after lazy-load success
    - `module.degraded` — Published by Orchestrator after module failure

14.4. **Delivery Guarantees:**
    - Same-type events: FIFO order.
    - Cross-type events: No ordering guarantee.
    - Delivery: At-most-once. A subscriber callback that raises is logged; other subscribers still receive the event.
    - Concurrency: Each subscriber's callback is scheduled via `asyncio.create_task()` — callbacks run concurrently, not sequentially.

14.5. **Backpressure:**
    - Pending queue limit: `config.event_bus.max_queue_size` (default 1000).
    - `low` priority events: dropped when queue is full.
    - `high` and `normal`: publisher blocks until space is available.

14.6. **Subscription:** Modules subscribe via `orchestrator.on(event_type, callback)` during boot Step 7. A module must unsubscribe during `async_shutdown()` to avoid stale references.

14.7. **No Direct Publishing:** Modules do not hold a reference to the Event Bus. A module that needs to publish an event must call a method on the Orchestrator (e.g., `orchestrator.emit(event_type, data)`). The Orchestrator validates the event and forwards it to the bus.

---

## 15. LLM Provider Contracts

15.1. **Unified Interface:** Every LLM provider adapter implements `LLMPort` (defined in `backend/modules/llm/ports/llm_port.py`).

15.2. **LLMPort Methods:**
    - `async generate(prompt: str, context: list[Message], tools: list[ToolDef] | None = None) -> LLMResponse`
    - `async count_tokens(text: str) -> int`

15.3. **LLMResponse Schema:**
```
LLMResponse:
  text: str                              # Response text
  tool_calls: list[ToolCall] | None      # Structured tool requests
  finish_reason: Literal["stop", "tool_calls", "length", "error"]
  token_usage: TokenUsage                # prompt_tokens, completion_tokens, total_tokens
  provider: str                          # Name of provider that served this response
  duration_ms: float                     # Wall-clock time
```

15.4. **Fallback Chain:** If a provider returns a 5xx, rate-limit error, or times out, the LLM Manager retries with the next provider in `config.llm.fallback_chain`. If all providers fail, the Orchestrator returns a user-facing error.

15.5. **Streaming:** Streaming responses are optional for initial implementation. When supported, the LLM Manager must expose `async generate_stream(...) -> AsyncIterator[str]` per the `LLMPort` extension.

15.6. **Tool-Use Protocol:** When the LLM returns `tool_calls`, those calls are routed through the Orchestrator (Phase 6 of `19_Request_Lifecycle.md`). Tool results are sent back to the LLM for a second-pass response.

15.7. **Context Preservation:** The LLM Manager must not modify or retain copies of the conversation history. All history management is the Context Manager's responsibility.

---

## 16. Memory Contracts

16.1. **Two Stores:** The memory subsystem has two logical stores:
    - **Conversation Store (SQLite):** Persistent message history, session data, user preferences.
    - **Semantic Index (JSON + NumPy):** Lightweight vector index for keyword-based retrieval. No external vector database.

16.2. **MemoryPort (defined in `backend/modules/context/ports/memory_port.py`):**
    - `async store_message(session_id: str, message: Message) -> None`
    - `async get_history(session_id: str, limit: int = 50) -> list[Message]`
    - `async store_setting(key: str, value: Any) -> None`
    - `async get_setting(key: str) -> Any | None`
    - `async health_check() -> bool`

16.3. **VectorIndexPort (defined in `backend/modules/memory/ports/vector_index_port.py`):**
    - `async index(keywords: list[str], source_id: str) -> None`
    - `async search(query: str, top_k: int = 5) -> list[SearchResult]`

16.4. **SQLite Policy:**
    - Single connection, opened at boot and closed at shutdown.
    - WAL mode enabled for read concurrency.
    - Schema migrations: tracked via a `_schema_version` table. Migrations are applied in order during `async_init()`.
    - No user data is ever deleted automatically. Expired sessions are archived, not deleted.

16.5. **No Vector Server:** The semantic index must not require a running server (ChromaDB, Qdrant, etc.). NumPy/JSON flat-file indexes are the only permitted implementation.

---

## 17. Plugin Contracts

(Applies when Phase 6 of `13_Roadmap.md` is implemented.)

17.1. **Plugin Interface:** Every plugin implements `PluginPort` (defined in `backend/modules/plugin/ports/plugin_port.py`).

17.2. **PluginPort Methods:**
    - `async init(config: dict, logger: Logger) -> None`
    - `async execute(action: str, args: dict) -> PluginResult`
    - `async shutdown() -> None`
    - `capabilities() -> list[str]`  # Returns list of tool names this plugin provides

17.3. **Layer Assignment:** Every plugin is assigned to exactly one of the six layers. It must obey the dependency rules of that layer.

17.4. **Isolation:** A plugin must not `import` any Naira-OS internal module except:
    - `PluginPort` (its base class)
    - `utils/` and `security/` (cross-cutting)
    - Ports from the layer below it (via the plugin system's dependency injection)
    - Standard library and installed third-party packages

17.5. **Registration:** Plugins register via the Plugin Manager, which reports their capabilities to the Capability Manager. Plugins must not self-register.

17.6. **Security:** A plugin that requests dangerous capabilities (file write, process execution) must be explicitly approved by the user during plugin installation. This approval is stored in `config/user.yaml`.

---

## 18. Security Contracts

18.1. **No Secrets in Code:** This is absolute. Zero API keys, credentials, paths, or passwords in any `.py` file. See `09_Security.md` §1.

18.2. **Sandbox Paths:**
    - Allowed: project root (`AI_Assistant/*`) and user-registered directories.
    - Blocklisted: `C:\Windows\*`, `C:\Program Files\*`, `C:\Program Files (x86)\*`, system Registry, system driver paths.
    - See `09_Security.md` §2 for the full list.

18.3. **Permission Gatekeeper:** Every PC control action passes through the Permission Gatekeeper before execution. The gate evaluates whether the action is safe (auto-execute) or dangerous (user prompt). Dangerous actions are logged and require explicit confirmation.

18.4. **Permission Sessions:** The user may grant time-bound permission sessions (e.g., "Allow file operations for 10 minutes"). Sessions auto-expire.

18.5. **Prompt Injection Guardrails (Phase 1):**
    - Input length limit: `config.security.max_input_length` (default 32 768 characters).
    - Control character filter: reject raw control characters except `\n`, `\t`.
    - Regex pattern blocklist for known injection patterns (Phase 1 baseline; enhanced in Phase 5+).
    - Future: LLM-as-judge, structured output parsing.

18.6. **Audit Logging:** All credential loading, file modification, terminal execution, and permission events are logged in a structured audit trail. See §8.6.

18.7. **Telemetry:** All telemetry is strictly offline. No data is sent to external endpoints. See `07_Module_Design.md` §1.E.

---

## 19. File and Folder Naming Rules

19.1. **Python Files:** `snake_case.py`. No hyphens, no spaces.

19.2. **Directories:** `snake_case/`. Matches the module name (e.g., `backend/modules/voice/`).

19.3. **Classes:** `PascalCase` (e.g., `LLMManager`, `SQLiteMemoryAdapter`, `PermissionGatekeeper`).

19.4. **Functions and Methods:** `snake_case()` (e.g., `process_request()`, `build_context()`).

19.5. **Variables:** `snake_case` (e.g., `session_id`, `tool_calls`, `app_config`).

19.6. **Constants:** `UPPER_SNAKE_CASE` (e.g., `MAX_INPUT_LENGTH`, `DEFAULT_TIMEOUT_S`).

19.7. **Private Members:** Prefix with single underscore: `_internal_method()`, `_internal_state`. Double underscore (`__name_mangling`) is discouraged — use a single underscore instead.

19.8. **Type Aliases:** Use the `type` keyword (Python 3.12+): `type JSON = dict[str, Any]`.

19.9. **Test Files:** Mirror the module path with `test_` prefix: `test_llm_manager.py`, `test_context_manager.py`.

19.10. **Template Files:** `backend/modules/prompt/templates/` uses `.j2` (Jinja2) extension for prompt templates.

19.11. **Configuration Files:** `config/` uses `.yaml` extension (not `.yml` — consistency within the project). Schema files use `.schema.json`.

---

## 20. Python Coding Standards

20.1. **Python Version:** 3.12+ only. Features from 3.12 (type parameter syntax `[T]`, `override` decorator, `Self` type) are expected. Features from older versions with newer alternatives (e.g., `os.path` vs `pathlib.Path`) should use the newer form.

20.2. **Type Annotations Required:** Every function and method must have type annotations for all parameters and return values. `Any` is permitted only for truly dynamic data (e.g., JSON payloads).

20.3. **Data Classes:** Use `@dataclass(frozen=True)` for immutable data objects (requests, responses, config snapshots). Use `@dataclass` for mutable state objects (session state, module state) with explicit mutability.

20.4. **Enums:** Use `StrEnum` (Python 3.12+) for string-valued enums (states, event types, source literals).

20.5. **Path Handling:** Use `pathlib.Path` exclusively. No `os.path.join()`, `os.path.exists()`, or string path manipulation.

20.6. **String Formatting:** Use f-strings exclusively. No `%` formatting, no `.format()`.

20.7. **Imports:** Standard library → third-party → local. Groups separated by a blank line. Absolute imports preferred. `from module import name` preferred over `import module` when importing specific functions or classes.

20.8. **Docstrings:** Every public class, method, and function must have a docstring (Google-style or NumPy-style). Private functions and methods: docstring optional but encouraged for non-trivial logic.

20.9. **Line Length:** 100 characters maximum.

20.10. **Linting:** The project uses `ruff` with the rulesets defined in `pyproject.toml`. The following rules are always enabled:
    - All `F` (Pyflakes) rules.
    - All `E` and `W` (Pycodestyle) rules, with `E501` (line length) set to 100.
    - `I` (isort) rules.
    - `N` (pep8-naming) rules.
    - `B` (flake8-bugbear) rules.
    - `ANN` (flake8-annotations) rules for public API.
    - `SIM` (flake8-simplify) rules.

20.11. **No Mutable Default Arguments:** Function and method signatures must not use mutable default arguments (`def f(x=[])`). Use `None` and create the default inside the function body.

20.12. **No Star Imports:** `from module import *` is forbidden everywhere.

---

## 21. Versioning Rules

21.1. **Scheme:** Semantic Versioning 2.0 (`MAJOR.MINOR.PATCH`).

21.2. **MAJOR:** Bumped when:
    - A breaking change is made to a Port interface.
    - A module is removed from the architecture.
    - A boot/shutdown step is reordered or removed.
    - A layer contract changes (e.g., a module moves to a different layer).
    - This document (§21 and §25) is modified.

21.3. **MINOR:** Bumped when:
    - A new module is added to the architecture (new entry in `backend/modules/`).
    - A new Port is added.
    - A new event channel is added.
    - A new LLM provider adapter is added.
    - A new feature flag is added.
    - A roadmap phase is completed.

21.4. **PATCH:** Bumped when:
    - A bug is fixed.
    - A log message is corrected.
    - Documentation is updated.
    - Dependencies are updated (with compatible version ranges).
    - Tests are added or improved.

21.5. **Version Location:** The canonical version is stored in `backend/__init__.py` as `__version__ = "X.Y.Z"`. The version string follows PEP 440.

21.6. **Pre-Release:** Experimental modules reside in a separate `backend/modules/experimental/` directory and are exempt from SemVer guarantees. They may be removed or changed without a MAJOR bump.

---

## 22. Documentation Rules

22.1. **Every Module Has a Doc in `docs/`:** When a module is added to `backend/modules/`, a corresponding markdown document must be created or the existing module spec (in `07_Module_Design.md` or a sub-page) must be updated.

22.2. **Document Format:** All docs use GitHub-flavoured Markdown. Use tables for structured data, diagrams in ASCII (not images), and code blocks with language tags.

22.3. **Cross-Referencing:** A document must reference the relevant sections of `21_System_Contracts.md` for every rule it implements. Example: "See `21_System_Contracts.md §15` for LLM provider contracts."

22.4. **Why Over How:** Documentation should explain why a design decision was made, not just what the code does. The code is the "how"; the docs are the "why".

22.5. **Changelog:** `16_Changelog.md` must be updated for every release with each change referenced to its issue number and/or commit hash.

22.6. **Empty Stubs:** Empty doc files (current placeholders like `01_Project_Vision.md`, `02_SRS.md`, etc.) must be filled before the corresponding implementation phase begins. An empty doc stub awaiting content must contain a single comment: `<!-- TODO: populate before Phase N implementation -->`.

---

## 23. Testing Rules

23.1. **Framework:** pytest with `pytest-asyncio` for async tests.

23.2. **Coverage Target:** Minimum 80% line coverage for `backend/` code. Coverage is measured per-module, not aggregated.

23.3. **Test Location:** Tests live in `testing/unit/` and `testing/integration/`, mirroring the module structure.
    - `testing/unit/modules/llm/test_llm_manager.py` tests `backend/modules/llm/llm_manager.py`.
    - `testing/unit/test_orchestrator.py` tests `backend/orchestrator.py`.

23.4. **Unit Test Rules:**
    - No external I/O. All network calls, database calls, and subprocess calls must be mocked or replaced with test doubles.
    - Test the module's public API (the class exported from `__init__.py`). Private functions are tested through the public API.
    - One test file per production file.

23.5. **Integration Test Rules:**
    - Test the wiring between modules (e.g., Context Manager → SQLite Memory Adapter).
    - Test the full Mediator path (CLI input → Orchestrator → LLM Manager → response).
    - Integration tests may perform real I/O to a test database (`testing/test_data/`).
    - Integration tests must not call external LLM APIs. Use a mock provider.

23.6. **Test Isolation:** Tests must not share state. Each test creates its own instances. The order of test execution must not matter.

23.7. **Async Tests:** Use `@pytest.mark.asyncio` for async test functions. Use `pytest-asyncio` event loop fixtures. Do not share the event loop across tests.

23.8. **Test Fixtures:** Common fixtures (mock `AppConfig`, mock `Logger`, mock `EventBus`) live in `testing/conftest.py`.

---

## 24. Future Compatibility Rules

24.1. **Backward Compatibility for Ports:** A Port interface must not be changed in a PATCH release. Adding methods to a Port requires a MINOR version. Removing or changing methods requires a MAJOR version.

24.2. **Deprecation Policy:** Before a Port method, a module, or a feature flag is removed, it must be deprecated for at least one MINOR release. Deprecated items are annotated with a `@deprecated` decorator (wrapper) or a comment referencing the version of deprecation.

24.3. **Experimental Modules:** Modules in `backend/modules/experimental/` are excluded from all backward-compatibility guarantees. They may be removed, renamed, or changed arbitrarily. No production deployment depends on an experimental module.

24.4. **Configuration Forward Compatibility:** Unknown keys in configuration files must be ignored (not rejected) to allow newer config files to work with older versions of the application.

24.5. **Event Channel Forward Compatibility:** Unknown event types on the Event Bus must be ignored (not rejected). A subscriber that does not recognise an event type silently drops it.

24.6. **Plugin API Stability:** Once a plugin API is released (Phase 6), plugins written against version X must work unmodified with version X.Y (where Y > 0) of the core.

---

## 25. Non-Negotiable Rules

These rules cannot be overridden, deprecated, or relaxed without a documented architecture decision signed off by the Lead Architect.

| # | Rule | Rationale |
|---|---|---|
| 25.1 | **No secrets in code.** Zero exceptions. | A single leaked API key compromises the user's account. |
| 25.2 | **Downward-only dependency rule.** Layer N must never import Layer N-1. | Violation creates circular dependencies and makes testing impossible. |
| 25.3 | **No modules calling each other directly.** All inter-module communication goes through the Orchestrator. | Direct module calls create tight coupling and prevent independent refactoring. |
| 25.4 | **Asyncio only.** No threading for I/O. No `time.sleep()`. | Threading on a dual-core i3 causes CPU starvation. Asyncio is the mandated concurrency model. |
| 25.5 | **Single entry point:** `main.py` → `asyncio.run(main())`. | Multiple entry points create inconsistent startup behaviour. |
| 25.6 | **Constructor injection only.** No service locator, no global state. | Service locators hide dependencies and prevent static analysis. |
| 25.7 | **Boot fails on environment and configuration errors.** | Running with invalid configuration is more dangerous than not running. |
| 25.8 | **Ports are the only way to cross layers.** Direct imports that skip a layer are rejected at code review. | Skipping layers destroys the architecture's separation of concerns. |
| 25.9 | **All user-facing errors are safe.** A crash must never leak a stack trace, memory address, or internal path to the user. | Security principle: maximum information hiding from untrusted output channels. |
| 25.10 | **Telemetry is strictly offline.** No data is sent to external servers. | User trust requires that the assistant has no phone-home capability. |
| 25.11 | **No star imports.** Every imported name is explicit. | Star imports hide dependencies and break static analysis. |
| 25.12 | **Type annotations on all public API.** | Python 3.12 has mature typing support; untyped code is legacy code. |

---

## 26. PC Control Port Contracts

The PC Control module (`backend/modules/pc_control/`) provides OS automation and system-settings manipulation through a hexagonal port/adapter architecture. The `PCControlPort` ABC (`backend/modules/pc_control/ports/pc_control_port.py`) is the sole contract boundary; all adapters implement this ABC.

### 26.1 Port Overview

26.1.1. **Canonical Port:** `PCControlPort` (ABC in `backend/modules/pc_control/ports/pc_control_port.py`).

26.1.2. **Adapters:**
- `LocalPCControlAdapter` — placeholder; `is_available` returns `False`, all methods raise `PCControlNotImplementedError`.
- `ProductionPCControlAdapter` — real driver-backed adapter; dispatches per-OS via `platform.system()` and subprocess helpers.

26.1.3. **Execution Layer:** `PCControlExecutor` wraps every port method with `asyncio.wait_for()` timeout and `ToolResult` error isolation. `PCControlManager` delegates to the executor for all public API calls.

26.1.4. **Component Delegators:** Thin classes (`PCMouse`, `PCKeyboard`, `PCClipboard`, `PCFilesystem`, `PCWindowManager`, `PCProcessManager`, `PCApplicationLauncher`, `PCNotification`, `PCPower`, `PCVolume`, `PCScreen`, `PCSystemSettings`, `PCSoftwareManager`, `PCAccountManager`) each take a `PCControlPort` and forward calls. These exist for logical grouping; they add no business logic.

### 26.2 Method Groups

The port is organised into clearly delimited sections. Every method is `async`.

#### Desktop Automation (pre-existing)

| Group | Methods |
|---|---|
| Mouse | `mouse_get_position`, `mouse_move_to`, `mouse_click`, `mouse_double_click`, `mouse_right_click`, `mouse_drag`, `mouse_scroll` |
| Keyboard | `keyboard_type_text`, `keyboard_press_key`, `keyboard_hotkey` |
| Clipboard | `clipboard_get_text`, `clipboard_set_text`, `clipboard_clear` |
| Filesystem | `filesystem_list_directory`, `filesystem_read_file`, `filesystem_write_file`, `filesystem_delete_file`, `filesystem_create_directory`, `filesystem_delete_directory`, `filesystem_zip_directory`, `filesystem_extract_archive`, `filesystem_copy_item`, `filesystem_move_item` |
| Windows | `window_list`, `window_get_active`, `window_focus`, `window_minimize`, `window_maximize`, `window_close`, `window_resize`, `window_move` |
| Processes | `process_list`, `process_kill` |
| App Launch | `launch_application` |
| Notifications | `notification_show` |
| Power | `power_shutdown`, `power_restart`, `power_sleep`, `power_hibernate`, `power_lock` |
| Volume | `volume_get`, `volume_set`, `volume_mute` |
| Screen | `screen_get_size`, `screen_capture`, `screen_list_displays` |
| System Metrics | `get_system_metrics`, `get_open_ports` |

#### System Settings (Phase 4.2)

| Sub-group | Methods | Parameters / Return |
|---|---|---|
| Wi-Fi | `wifi_set_power(enabled: bool)` | Toggle adapter on/off |
| | `wifi_get_power() → bool` | Current power state |
| | `wifi_list_networks() → list[WifiNetwork]` | Scan nearby SSIDs |
| | `wifi_connect(ssid, password?)` | Connect to a network |
| Bluetooth | `bluetooth_set_power(enabled: bool)` | Toggle adapter on/off |
| | `bluetooth_get_power() → bool` | Current power state |
| | `bluetooth_list_devices() → list[BluetoothDevice]` | Scan/list paired devices |
| | `bluetooth_pair(device_address, pin?)` | Pair with a device |
| Display | `display_get_brightness() → int` | 0–100 percentage |
| | `display_set_brightness(level: int)` | Set brightness |
| | `display_get_resolution() → tuple[int, int]` | Current width×height |
| | `display_set_resolution(width, height)` | Change resolution |
| | `display_list_resolutions() → list[tuple[int,int]]` | Supported modes |
| | `display_set_night_light(enabled: bool)` | Blue-light filter |
| | `display_get_night_light() → bool` | Current state |
| | `display_set_dark_mode(enabled: bool)` | System dark theme |
| | `display_get_dark_mode() → bool` | Current state |
| Power Settings | `power_set_airplane_mode(enabled: bool)` | Radio kill-switch |
| | `power_get_airplane_mode() → bool` | Current state |
| | `power_set_do_not_disturb(enabled: bool)` | Focus/DND mode |
| | `power_get_do_not_disturb() → bool` | Current state |

#### Software Management (Phase 4.2)

| Method | Parameters / Return |
|---|---|
| `software_list_installed() → list[InstalledPackage]` | Inventory of installed packages |
| `software_install(package: str) → PackageOpResult` | Install via native package manager |
| `software_uninstall(package: str) → PackageOpResult` | Uninstall via native package manager |
| `software_check_update(package: str) → bool` | Check if update available |

#### User Account Management (Phase 4.2)

| Method | Parameters / Return |
|---|---|
| `account_list_users() → list[UserAccount]` | All local user accounts |
| `account_get_current_user() → UserAccount` | Currently logged-in user |
| `account_create_user(username, password?) → UserAccount` | Create standard (non-admin) local user |
| `account_set_enabled(username, enabled: bool)` | Enable/disable an account |
| `account_modify_groups(username, add?, remove?)` | Change group membership |

### 26.3 Type Contracts

All types are frozen `@dataclass` (immutable) unless explicitly mutable. Defined in `backend/modules/pc_control/_types.py`.

```
WifiNetwork:
    ssid: str
    signal_strength: int  # 0–100
    secured: bool

BluetoothDevice:
    name: str
    address: str          # MAC address
    paired: bool
    trusted: bool

DisplaySettings:
    brightness: int       # 0–100
    width: int
    height: int
    refresh_rate: float

InstalledPackage:
    name: str
    version: str
    publisher: str
    install_date: str     # ISO format

PackageOpResult:          # @dataclass (mutable)
    success: bool
    package: str
    message: str

UserAccount:
    username: str
    full_name: str
    enabled: bool
    admin: bool
```

### 26.4 Exception Hierarchy

All exceptions inherit from `PCControlError` → `NairaError`.

| Exception | Semantics |
|---|---|
| `PCControlUnsupportedPlatformError` | The operation is not supported on the current OS or the required hardware (e.g. Bluetooth adapter) is absent. |
| `PCControlPackageManagerNotFoundError` | No supported package manager (winget/apt/dnf/pacman/brew) was detected on the system. |
| `PCControlNotImplementedError` | Raised by the placeholder adapter to signal no real driver is configured. |
| `PCControlPermissionError` | The operation was denied by the sandbox or security policy. |
| `PCControlExecutionError` | A subprocess or OS call failed during execution. |
| `PCControlTimeoutError` | The operation exceeded its timeout. |

### 26.5 Cross-Platform Dispatch Pattern

26.5.1. The `ProductionPCControlAdapter` detects the host OS at runtime via `platform.system()` and dispatches to OS-specific private helpers within each method's synchronous closure.

26.5.2. **OS-specific CLI tools used:**

| Capability | Windows | macOS | Linux |
|---|---|---|---|
| Wi-Fi | `netsh wlan` / `netsh interface` | `networksetup` | `nmcli` |
| Bluetooth | *(unsupported)* | `blueutil` | `bluetoothctl` |
| Display brightness | `powershell WmiSetBrightness` | `brightness` CLI | `xrandr` / `brightnessctl` |
| Display resolution | `powershell Set-DisplayResolution` | *(not implemented)* | `xrandr` |
| Night light | Registry (`reg add/query`) | *(not implemented)* | `redshift` |
| Dark mode | Registry | `defaults write` | `gsettings` |
| Airplane mode | Registry / `netsh` | `networksetup` | `nmcli radio all` |
| DND | Registry (Focus Assist) | `defaults write` | `gsettings` |
| Package manager | `winget` | `brew` | `apt` / `dpkg-query` |
| User accounts | `net user` / `net localgroup` | `dscl` / `sysadminctl` / `dseditgroup` | `useradd` / `usermod` / `gpasswd` |

26.5.3. **Subprocess safety:** Every external command is executed via `subprocess.run(capture_output=True, text=True, timeout=30)`. `subprocess.TimeoutExpired` maps to `PCControlExecutionError`. `OSError` maps to `PCControlExecutionError`. Non-zero exit codes are checked by `_check_cmd()` and raise `PCControlExecutionError`. Raw `CalledProcessError` must never propagate.

26.5.4. **Unsupported platform fallback:** When `platform.system()` returns an unrecognised value, methods raise `PCControlUnsupportedPlatformError` via the `_unsupported()` helper. macOS methods that are not yet implemented raise `PCControlNotImplementedError` rather than silently failing.

### 26.6 Security Gating

26.6.1. **Dangerous operations set:** The `ProductionPCControlAdapter.DANGEROUS_OPERATIONS` frozenset includes: `wifi_connect`, `bluetooth_pair`, `software_install`, `software_uninstall`, `account_create_user`, `account_set_enabled`, `account_modify_groups` (in addition to pre-existing power/kill/delete operations). These require the operation name to be in the `allowed_commands` tuple when `sandbox_enabled` is `True`.

26.6.2. **Security policy rules** (`config/security_policy.json`):

| Tool Pattern | Mode | Risk Level | Requires Approval |
|---|---|---|---|
| `pc_software` | confirm | high | Yes |
| `pc_account` | admin | high | Yes |
| `pc_wifi` | confirm | high | Yes |
| `pc_bluetooth` | confirm | high | Yes |
| `pc_display` | confirm | medium | No |
| `pc_system_settings` | confirm | medium | No |

26.6.3. **Risk analyzer integration:** `pc_account`, `pc_software`, `pc_wifi`, `pc_bluetooth` are classified as HIGH risk tools. `pc_display`, `pc_system_settings` are MEDIUM risk. Dangerous argument combinations (e.g., `pc_account` + `create_user`) escalate to HIGH.

26.6.4. **Sandbox allow/deny lists:** Read-only operations (`wifi_get_power`, `wifi_list_networks`, `bluetooth_get_power`, `bluetooth_list_devices`, `display_get_*`, `power_get_*`, `software_list_installed`, `software_check_update`, `account_list_users`, `account_get_current_user`) are in the sandbox allowed list. All mutating operations are in the denied list and require explicit security approval.

26.6.5. **Explicit non-goals:** The PC Control module must NOT: bypass OS authentication/UAC/sudo prompts, disable security software or firewalls, perform remote or unattended privilege escalation, or weaken existing security policy tiers for other modules.

### 26.7 Lifecycle

26.7.1. `PCControlPort.close()` releases all driver resources. Implementations must be idempotent.

26.7.2. `PCControlPort.is_available` returns `True` only when the adapter is operational and not closed.

26.7.3. On platforms where a sub-capability genuinely cannot be supported (no Bluetooth adapter, no supported package manager), individual methods fail gracefully with `PCControlUnsupportedPlatformError` — the adapter does not crash or mark itself unavailable.

---

## 27. Browser Port & Automation Contracts

### 27.1 Overview & Architecture

27.1.1. The **Browser Module** (`backend/modules/browser/`) provides web navigation, search, automated page interaction, multi-tab session management, cookie/storage persistence, PDF export, and sandboxed file download capabilities for Naira OS.

27.1.2. Architecture follows strict **hexagonal / ports-and-adapters** design. `BrowserManager` (`browser_module.py`) is the **ONLY public class** in the module. All internal automation logic delegates to an abstract `BrowserPort` implementation (`PlaywrightBrowserAdapter` or fallback `LocalBrowserAdapter`).

### 27.2 Capability & Method Contracts

`BrowserPort` defines the complete abstract port interface:

| Method | Parameters | Return Type | Description |
|---|---|---|---|
| `navigate` | `url: str`, `timeout: float = 30.0`, `extract_content: bool = True`, `extra_http_headers: dict \| None = None`, `http_credentials: tuple \| None = None` | `BrowserPage` | Navigates to target URL and captures page snapshot. |
| `search` | `query: str`, `max_results: int = 10`, `timeout: float = 30.0` | `BrowserSearchResponse` | Performs search using primary/fallback selector chains. |
| `extract` | `url: str`, `timeout: float = 30.0` | `BrowserPage` | Fast static DOM content extraction. |
| `screenshot` | `url: str = ""`, `timeout: float = 30.0` | `bytes` | Captures active or specified page screenshot. |
| `back` | `timeout: float \| None = None` | `BrowserPage` | Navigates backward in tab history. |
| `forward` | `timeout: float \| None = None` | `BrowserPage` | Navigates forward in tab history. |
| `reload` | `timeout: float \| None = None` | `BrowserPage` | Reloads current page tab. |
| `new_tab` | `url: str = "about:blank"` | `str` | Opens new tab and returns tab identifier. |
| `close_tab` | `page_id: str \| None = None` | `None` | Closes specified or active tab. |
| `list_tabs` | None | `list[dict]` | Returns metadata for all open tabs. |
| `switch_tab` | `page_id: str` | `None` | Switches active tab context. |
| `get_cookies` | `urls: list[str] \| None = None` | `list[dict]` | Retrieves active browser cookies. |
| `set_cookies` | `cookies: list[dict]` | `None` | Sets cookies in browser context. |
| `clear_cookies` | None | `None` | Clears all cookies from browser context. |
| `upload_file` | `selector: str`, `file_paths: str \| list[str]` | `None` | Uploads file(s) to file input element. |
| `press_key` | `key: str`, `selector: str \| None = None` | `None` | Presses key on element or active page body. |
| `wait_for_selector` | `selector: str`, `state: str = "visible"`, `timeout: float = 30.0` | `None` | Explicitly waits for element visibility/actionability. |
| `select_option` | `selector: str`, `value: str \| list[str]`, `timeout: float = 30.0` | `None` | Selects option(s) in dropdown element. |
| `hover` | `selector: str`, `timeout: float = 30.0` | `None` | Hovers mouse cursor over element matching selector. |
| `right_click` | `selector: str`, `timeout: float = 30.0` | `None` | Right-clicks target element. |
| `drag_and_drop` | `source_selector: str`, `target_selector: str`, `timeout: float = 30.0` | `None` | Drags source element and drops onto target element. |
| `check` | `selector: str`, `timeout: float = 30.0` | `None` | Checks checkbox or radio input element. |
| `uncheck` | `selector: str`, `timeout: float = 30.0` | `None` | Unchecks checkbox input element. |
| `export_pdf` | `save_path: str = ""`, `timeout: float = 30.0` | `str` | Exports page as PDF (headless Chromium only). |
| `wait_for_download` | `timeout: float = 30.0` | `DownloadResult` | Waits for file download event and saves to sandboxed path. |
| `get_local_storage` | `key: str \| None = None` | `str` | Retrieves LocalStorage content or key. |
| `set_local_storage` | `key: str`, `value: str` | `None` | Sets LocalStorage key-value pair. |
| `clear_local_storage` | None | `None` | Clears LocalStorage for active origin. |
| `get_session_storage` | `key: str \| None = None` | `str` | Retrieves SessionStorage content or key. |
| `set_session_storage` | `key: str`, `value: str` | `None` | Sets SessionStorage key-value pair. |
| `clear_session_storage` | None | `None` | Clears SessionStorage for active origin. |

### 27.3 Data Contracts & Types

27.3.1. `BrowserPage` (`dataclass(frozen=True)`): Immutable page snapshot containing `url`, `title`, `content` (extracted plain text), `html`, `status_code`, and `headers`.

27.3.2. `BrowserTab` (`dataclass(frozen=True)`): Metadata representing a browser tab (`id`, `url`, `title`, `created_at`, `last_active_at`).

27.3.3. `DownloadResult` (`dataclass(frozen=True)`): File download outcome (`path`, `suggested_filename`, `size_bytes`, `url`).

### 27.4 Exception Hierarchy

All browser exceptions inherit from `BrowserError` (`NairaError`):

```
NairaError
└── BrowserError
    ├── BrowserNavigationError
    ├── BrowserSearchError
    ├── BrowserContentError
    ├── BrowserTimeoutError
    ├── BrowserSessionError
    ├── BrowserNotImplementedError
    ├── BrowserDownloadError
    └── BrowserPermissionError
```

### 27.5 Security Gating & Path Sandboxing

27.5.1. High-risk browser tools (`browser_execute_js`, `browser_download_file`, `browser_set_cookies`, `browser_clear_cookies`, `browser_set_local_storage`, `browser_clear_local_storage`, `browser_set_session_storage`, `browser_clear_session_storage`, `browser_upload_file`) are registered in `_HIGH_RISK_TOOLS` (`_risk_analyzer.py`) and `_SANDBOX_DENIED_ACTIONS` (`_sandbox_manager.py`).

27.5.2. `BrowserManager` routes high-risk tool invocations through `security_manager.check_tool_execution()`. Denied or unconfirmed actions return error `ToolResult` with security policy context.

27.5.3. All file download operations sanitize target paths using `BrowserDownloader` and validate security boundary rules using `PathValidator` (`backend/modules/security/_path_validator.py`).

### 27.6 Engine & Profile Configuration

27.6.1. Supports Chromium, Firefox, and WebKit browser engines via `browser_engine` configuration parameter.

27.6.2. Persistent browser profiles (cookies, cache, sessions across boots) are supported via `user_data_dir` configuration.

---

## Architecture Version

| Property | Value |
|---|---|
| Architecture Pattern | Micro-Kernel + 6-Layer Clean Architecture |
| Layers | Presentation, Application, AI Core, Service, Infrastructure, OS |
| Dependency Direction | Strictly downward (1 → 2 → 3 → 4 → 5 → 6) |
| Inter-Module Comms | Mediator Pattern (synchronous), Event Bus (async) |
| Concurrency | `asyncio` single-threaded + `to_thread()` for CPU-bound offload |
| Hardware Baseline | Intel i3 6th Gen, 4 GB RAM |
| Target Language | Python 3.12+ |
| Build System | (to be defined in `05_Tech_Stack.md`) |

## Document Version

| Property | Value |
|---|---|
| Document | 21_System_Contracts.md |
| Version | 1.2.0 |
| Status | Ratified |
| Author | Lead Architect |
| Ratification Date | Phase 4.2 |

## Compatibility

This document is compatible with:
- All documents in `docs/` that are non-empty at the time of ratification (`04_Architecture.md`, `06_Folder_Structure.md`, `07_Module_Design.md`, `09_Security.md`, `13_Roadmap.md`, `18_Boot_Sequence.md`, `19_Request_Lifecycle.md`, `20_Dependency_Rules.md`).
- Python 3.12+ standard library.
- Asyncio event loop model.
- Microsoft Windows 10/11 (target OS).

## Revision History

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.2.0 | 2026-08-02 | Lead Architect | Added §27 Browser Port & Automation Contracts — documenting full Playwright browser automation, element interactions, storage, PDF export, sandboxed downloads, and security gating. |
| 1.1.0 | 2026-08-02 | Lead Architect | Added §26 PC Control Port Contracts — documenting system settings, software management, and user account management capability surface. |
| 1.0.0 | 2026-07-12 | Lead Architect | Initial ratification. Canonical rules consolidated from Phase 0.5 documentation. |
