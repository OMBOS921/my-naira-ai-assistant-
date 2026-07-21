# 18. Boot Sequence & System Lifecycle

This document defines the precise startup and shutdown ordering of the Naira-OS system. It extends the FSM states defined in `04_Architecture.md` with `BOOTING` and `SHUTDOWN` states, and establishes the lifecycle contract every module must follow.

---

## 1. Finite State Machine (Extended)

The Orchestrator manages the following state machine. States **BOOTING** and **SHUTDOWN** are additions to the core states (`IDLE`, `LISTENING`, `PROCESSING`, `SPEAKING`) defined in `07_Module_Design.md`.

```
    ┌──────────┐
    │  BOOTING │  ← Entry point after main.py starts
    └────┬─────┘
         │ (boot succeeds)
         ▼
    ┌──────────┐
    │   IDLE   │  ← Awaiting user input
    └────┬─────┘
         │ (voice activity detected / text entered)
         ▼
    ┌────────────┐
    │  LISTENING │  ← Capturing input (microphone or CLI read)
    └────┬───────┘
         │ (transcription complete / input received)
         ▼
    ┌────────────┐
    │ PROCESSING │  ← LLM inference, tool execution
    └────┬───────┘
         │ (response ready, voice output required)
         ▼
    ┌──────────┐
    │ SPEAKING │  ← TTS playback (skipped for text-only responses)
    └────┬─────┘
         │ (playback complete)
         ▼
    ┌──────────┐
    │   IDLE   │
    └──────────┘

    Any state → SHUTDOWN (on SIGINT, SIGTERM, or user "exit" command)
```

### State Transition Rules

| Transition | Trigger | Condition |
|---|---|---|
| BOOTING → IDLE | Boot sequence Step 12 | All core modules registered, no fatal error |
| IDLE → LISTENING | Voice activity / CLI input | Microphone open or CLI readline active |
| LISTENING → PROCESSING | STT transcription done / Enter key | Input text is non-empty |
| PROCESSING → SPEAKING | LLM response contains speech flag | TTS engine is loaded and enabled |
| PROCESSING → IDLE | LLM response is text-only | No TTS required |
| SPEAKING → IDLE | TTS playback finished | Queue empty |
| * → SHUTDOWN | SIGINT / SIGTERM / "exit" | Always accepted |

---

## 2. Boot Sequence

All steps execute inside `main.py` under a single `asyncio.run(main())` entry point. Each step is sequential; a step must complete before the next begins.

```
main.py entry (asyncio.run)
│
├── Step  1: Environment Validation
├── Step  2: Configuration Loading
├── Step  3: Logger Initialization
├── Step  4: Security Manager Initialization
├── Step  5: Event Bus Creation
├── Step  6: Orchestrator Instantiation
├── Step  7: Core Module Registration
├── Step  8: Feature Flag Evaluation
├── Step  9: Adapter Wiring (Port Injection)
├── Step 10: Dynamic Module Readiness
├── Step 11: Presentation Layer Startup
│
└── FSM → IDLE
```

### Step 1: Environment Validation

- **Owner:** `main.py` / Configuration Manager
- **Action:**
  1. Verify `.env` exists at project root. If absent, log a warning and fall back to OS environment variables.
  2. Read all keys prefixed with a defined pattern (e.g., `NAIRA_*` or `*_API_KEY`).
  3. Validate required keys are non-empty. The required set is defined in `config/required_env.json`.
  4. Store validated key-value pairs in an immutable `EnvironmentSnapshot` (plain `dataclass`, not the `os.environ` dict).
- **Failure:** If a required key is missing, log the missing key name (not its value) and exit with code 1.
- **Asyncio:** Synchronous (runs before the event loop starts).

### Step 2: Configuration Loading

- **Owner:** Configuration Manager (`backend/modules/settings/`)
- **Action:**
  1. Scan `config/` directory for `*.yaml` and `*.json` files.
  2. Parse each file. Merge in priority order: `defaults.yaml` < `user.yaml` (user overrides defaults).
  3. Validate every value against a schema defined in `config/schemas/`.
  4. Expose as a frozen `AppConfig` dataclass tree.
- **Failure:** Schema violation → log the field path + expected type → exit with code 1. Missing file → use built-in defaults, log a warning.
- **Asyncio:** Synchronous (file I/O via stdlib).

### Step 3: Logger Initialization

- **Owner:** Logger (core kernel utility, lives conceptually in `backend/modules/utils/logger/`)
- **Action:**
  1. Create `logs/` directory if absent.
  2. Configure two handlers:
     - **File handler:** Daily rotating, max 10 MB per file, keep 30 days. Format: `logs/naira_YYYY-MM-DD.log`.
     - **Console handler:** stdout, level = INFO (adjustable from config).
  3. Set global log level from `config`.
  4. Install `sys.excepthook` to route uncaught exceptions through the logger.
- **Failure:** Cannot write to `logs/` → fall back to console-only logging, emit a single WARNING.
- **Asyncio:** Synchronous.

### Step 4: Security Manager Initialization

- **Owner:** Security Manager (`backend/modules/security/`)
- **Action:**
  1. Load the sandbox path rules (allowed and blocklisted directories) from `config/security.yaml`.
  2. Compile regex patterns for prompt injection detection (initial set; enhanced in Phase 5).
  3. Initialize the audit log writer (wraps the Logger with a structured security-specific format).
  4. Create a `PermissionGatekeeper` instance with no active sessions (all actions require approval).
- **Failure:** Malformed security config → log error → exit with code 1. Missing security config → use conservative defaults (everything blocked).
- **Asyncio:** Synchronous.

### Step 5: Event Bus Creation

- **Owner:** Orchestrator bootstrap
- **Action:**
  1. Instantiate a single `EventBus` (asyncio-native, in-memory pub/sub).
  2. The Event Bus lives as a singleton owned by the Orchestrator. No other component creates or owns it.
  3. Pre-register internal system channels: `system.shutdown`, `system.memory_warning`, `system.error`, `permission.granted`, `permission.revoked`.
- **Failure:** Not possible (pure in-memory allocation).
- **Asyncio:** Synchronous.

### Step 6: Orchestrator Instantiation

- **Owner:** `main.py`
- **Action:**
  1. Instantiate `Orchestrator` with:
     - Reference to `EventBus`
     - Reference to `Logger`
     - Reference to `AppConfig`
     - Empty module registry (dict of `str → ModuleInterface`).
  2. Orchestrator sets its internal FSM state to `BOOTING`.
  3. Register the Orchestrator's own shutdown handler on the `system.shutdown` event channel.
- **Failure:** Not possible (pure Python object construction).
- **Asyncio:** Synchronous.

### Step 7: Core Module Registration

- **Owner:** Orchestrator
- **Action:**
  1. Instantiate each **static** (always-loaded) module and register it with the Orchestrator's capability registry.
  2. **Static modules (load order matters):**
     ```
     1. Capability Manager   (Application Layer)
     2. Feature Flag Manager (Application Layer)
     3. Session Manager      (Application Layer)
     4. Context Manager      (AI Core Layer)
     5. Prompt Manager       (AI Core Layer)
     6. LLM Manager          (AI Core Layer)
     ```
  3. Registration means calling `orchestrator.register_module(name, instance)`. The instance must conform to `ModuleInterface` (defined in `20_Dependency_Rules.md`).
  4. Each static module receives its dependencies via constructor injection:
     ```python
     # Conceptual only — no code generated
     # llm_manager = LLMManager(config=app_config.llm, logger=logger)
     # orchestrator.register_module("llm", llm_manager)
     ```
- **Failure:** A module's `__init__` raises → log the error → mark that module as `degraded` and continue. The Capability Manager will skip degraded modules during routing.
- **Asyncio:** Mix of sync (construction) and async (if a module's `async_init()` coroutine is available).

### Step 8: Feature Flag Evaluation

- **Owner:** Feature Flag Manager
- **Action:**
  1. Read feature flags from `config/features.yaml`.
  2. Identify which dynamic modules are flagged as `load_on_start: true` vs `lazy: true`.
  3. For `lazy: true` modules, record their module path and factory in a lazy-load registry. They will be imported and instantiated on first use.
  4. Return the set of modules to preload.
- **Failure:** Corrupt feature flag file → treat all flags as `false` (safest default), log warning.
- **Asyncio:** Synchronous.

### Step 9: Adapter Wiring (Port Injection)

- **Owner:** Orchestrator bootstrap
- **Action:**
  1. Resolve all Port/Adapter bindings defined in `config/ports.yaml`.
  2. For each binding, instantiate the Adapter class and inject it into the Port-owning module.
  3. **Required bindings:**
     ```
     Port                                  Adapter
     ──────────────────────────────────────────────────────────
     context.MemoryPort                    memory.SQLiteMemoryAdapter
     llm.LLMPort                           llm.GeminiAPIAdapter (or OllamaAdapter)
     memory.VectorIndexPort                memory.JSONVectorIndexAdapter
     ```
  4. Bindings are created once at boot. The Orchestrator holds the wired module graph.
- **Failure:** An Adapter class cannot be imported → mark dependent module as `degraded`, log error, continue. The system boots in a degraded but functional state.
- **Asyncio:** Synchronous.

### Step 10: Dynamic Module Readiness

- **Owner:** Orchestrator
- **Action:**
  1. For modules flagged as `load_on_start: true` in Step 8, invoke their `async_init()` if present.
  2. `async_init()` is an optional coroutine that performs heavy one-time setup (e.g., loading a Whisper model, opening a database connection).
  3. Each module has a deadline (configurable, default 30 s). If `async_init()` exceeds the deadline, the module is marked as `degraded` and unloaded.
- **Failure:** A module's `async_init()` times out or raises → log error → mark `degraded` → continue.
- **Asyncio:** Concurrent (all `async_init()` coroutines run in parallel via `asyncio.gather(..., return_exceptions=True)`).

### Step 11: Presentation Layer Startup

- **Owner:** Orchestrator
- **Action:**
  1. Start the CLI console reader as an asyncio task.
  2. If WebSocket server is enabled in config, start it as a separate asyncio task.
  3. Both tasks send `UserRequest` objects to the Orchestrator via a callable reference (not by importing the Orchestrator — the reference is injected during wiring).
- **Failure:** CLI fails to start → fatal (no user I/O possible), exit. WebSocket fails → log warning, continue with CLI only.
- **Asyncio:** Async (tasks are created and scheduled on the event loop).

### Step 12: System Ready

- **Owner:** Orchestrator
- **Action:**
  1. Orchestrator transitions FSM to `IDLE`.
  2. Log boot summary: `[BOOT] System ready in X.XXs. Modules: N active, M lazy, D degraded.`
  3. CLI prints the prompt and awaits input.
- **Asyncio:** The event loop is now running and processing events.

---

## 3. Dynamic Module Lazy-Loading

Modules flagged as `lazy: true` in `config/features.yaml` follow this contract:

1. The Feature Flag Manager stores a factory callable (not the module instance).
2. On first request routed to that capability, the Orchestrator calls:
   ```
   module = factory()          # import + instantiate
   await module.async_init()   # heavy setup
   ```
3. If the module cannot be loaded (import error, timeout, OOM), the Orchestrator logs the failure, marks the module as `degraded`, and returns an error message to the user.
4. When the module is idle for `config.modules.unload_after_seconds` (default 300 s), the Orchestrator may:
   - Call `module.async_shutdown()` if defined
   - Delete all references
   - Invoke `gc.collect()`

---

## 4. Shutdown Sequence

Triggered by: SIGINT, SIGTERM, user typing "exit", or fatal internal error.

```
FSM → SHUTDOWN (from any state)
│
├── Step S1: Presentation Shutdown
├── Step S2: Dynamic Module Unload (reverse registration order)
├── Step S3: Session Persist
├── Step S4: Event Bus Drain
├── Step S5: Logger Flush
├── Step S6: Configuration Backup
├── Step S7: Orchestrator Stop
│
└── asyncio event loop closes
```

### Step S1: Presentation Shutdown
- Stop CLI readline task. Cancel WebSocket server task.
- Grace period: 3 s. Force cancel after expiry.

### Step S2: Dynamic Module Unload
- Iterate modules in **reverse** registration order.
- For each: call `module.async_shutdown()` if defined (grace period 5 s per module), then delete reference.

### Step S3: Session Persist
- Session Manager flushes active session data to SQLite (via MemoryPort).
- This is a single synchronous write; timeout 2 s.

### Step S4: Event Bus Drain
- Stop accepting new events.
- Process remaining events in the queue (max 100 ms wait).

### Step S5: Logger Flush
- Flush all buffered log handlers.
- Close file handles.

### Step S6: Configuration Backup
- If any configuration was modified at runtime, write current state to `config/.runtime_backup.yaml`.

### Step S7: Orchestrator Stop
- Orchestrator sets FSM to `SHUTDOWN` (terminal state).
- Release all internal references.
- Return from `main()`.

---

## 5. Crash Recovery

The system does not attempt automatic crash recovery. On restart, it performs a full boot sequence.
- Logs from the previous session are available in `logs/` for diagnostics.
- If the SQLite database was left in an unclean state (detected via a write-ahead log flag), the Memory Manager runs a `PRAGMA integrity_check` and logs the result. Corrupt databases are renamed with a `.corrupt` suffix and a fresh database is created.
