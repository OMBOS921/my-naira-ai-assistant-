# 20. Dependency Rules & Layer Contracts

This document defines the strict import rules, module isolation boundaries, and the Port/Adapter pattern for cross-layer communication. Every module added to the system must conform to these rules.

---

## 1. The 6-Layer Dependency Graph

Each of the six layers defined in `04_Architecture.md` maps to a set of modules in `backend/modules/`. Code dependencies flow strictly **downward**. A layer may import from itself, the layer immediately below it, or cross-cutting modules. It must never import from a higher layer.

```
   Layer                         Modules in backend/modules/
   ─────────────────────────────────────────────────────────
   1. PRESENTATION               avatar/
   2. APPLICATION                capability/, session/, plugin/, settings/, permissions/, telemetry/, update/
   3. AI CORE                    llm/, prompt/, context/  (+ orchestrator.py)
   4. SERVICE                    voice/, vision/, browser/, file_manager/
   5. INFRASTRUCTURE             memory/
   6. OPERATING SYSTEM           pc_control/

   Cross-cutting (no layer)     security/, utils/
```

### Strict Dependency Rule

| Layer | May Import From |
|---|---|
| 1 (Presentation) | Cross-cutting, Layer 2 |
| 2 (Application) | Cross-cutting, Layer 3 |
| 3 (AI Core) | Cross-cutting, Layer 4 **via Ports only** |
| 4 (Service) | Cross-cutting, Layer 5, Layer 6 |
| 5 (Infrastructure) | Cross-cutting, Layer 6 |
| 6 (OS) | Cross-cutting (`utils/` only) |
| Cross-cutting | Nothing from `backend/` (must be self-contained) |

**Exceptions:**
- All layers may import the Logger (housed in `utils/logger/`).
- All layers may import type definitions from `backend/__init__.py` only if they are pure types (dataclasses, enums, Protocols) with no import chains into restricted layers.
- The Orchestrator (`backend/orchestrator.py`) is an exception to the one-hop rule: it may hold references to any module's public interface, but only via dependency injection (constructor injection at boot time, not via `import` statements).

---

## 2. The Port/Adapter Pattern (Dependency Inversion)

When a higher layer needs a service from a non-adjacent lower layer (e.g., Layer 3 AI Core needs Layer 5 Infrastructure for persistence), direct import is **forbidden**. Instead, the higher layer defines a **Port**, and the lower layer implements an **Adapter**.

### Pattern Definition

```
Layer N (Consumer)                Layer N+2 or below (Provider)
┌──────────────────────┐          ┌──────────────────────────┐
│  ports/              │          │  adapters/               │
│  ├── ServicePort.py  │◄─────────┤  ├── ConcreteAdapter.py  │
│  │   (ABC/Protocol)  │          │  │   (implements Port)   │
│  └───────────────────┘          └──────────────────────────┘
```

- The **Port** lives in a `ports/` subpackage inside the consumer module.
- The **Adapter** lives in an `adapters/` subpackage inside the provider module.
- The consumer never imports the adapter directly.
- The adapter never imports the consumer's non-port code.

### Required Ports

| Consumer Module | Port | Adapter Module | Adapter |
|---|---|---|---|
| `backend/modules/context/` | `memory_port.py` → `MemoryPort` | `backend/modules/memory/` | `SQLiteMemoryAdapter` |
| `backend/modules/llm/` | `llm_port.py` → `LLMPort` | `backend/modules/llm/providers/` | `GeminiAPIAdapter`, `OllamaAdapter`, `DeepSeekAdapter` |
| `backend/modules/memory/` | `vector_index_port.py` → `VectorIndexPort` | `backend/modules/memory/` | `JSONVectorIndexAdapter` |


### Wiring

Port/Adapter bindings are created at boot time (Step 9 in `18_Boot_Sequence.md`). The Orchestrator or `main.py` instantiates each Adapter and injects it into the consumer's constructor. No service locator, no global state, no `import` of adapter classes from consumer code.

```
# Conceptual wiring (no code generation)
adapter = SQLiteMemoryAdapter(config=appConfig)
context = ContextManager(memory_port=adapter)
orchestrator.register_module("context", context)
```

---

## 3. Per-Module Layer Assignment

### Layer 1 — Presentation

| Module | Allowed Imports | Forbidden Imports |
|---|---|---|
| `avatar/` | `security/`, `utils/`, `settings/` (via AppConfig injection), `orchestrator.py` (via injected reference only) | Any Layer 3, 4, 5, 6 module directly |

This module is a Phase 6 placeholder. It sends/receives data over TCP/socket to an external 3D rendering process. It must not perform AI inference, access the database, or execute system commands. All data passed to/from the avatar is opaque byte payloads; interpretation is the Orchestrator's responsibility.

### Layer 2 — Application

| Module | Allowed Imports | Forbidden Imports |
|---|---|---|
| `capability/` | `security/`, `utils/`, `settings/` (via AppConfig injection), `orchestrator.py` (via injected reference only) | Any Layer 3, 4, 5, 6 module directly |
| `session/` | `security/`, `utils/`, `context/` (via MemoryPort for session persistence) | Any Layer 1, 4, 5, 6 module directly |
| `plugin/` | `security/`, `utils/`, `settings/` (via AppConfig injection), Layer 3 via Orchestrator only | Any Layer 4, 5, 6 module directly |
| `settings/` | `security/`, `utils/`; receives `AppConfig` via constructor injection | Any Layer 1 module |
| `permissions/` | `security/`, `utils/`, `settings/` (via AppConfig injection) | Any Layer 1, 3+ module |
| `telemetry/` | `utils/`, `memory/` (via MemoryPort for metric storage) | Any Layer 1, 3, 4, 6 module directly |
| `update/` (Phase 6) | `security/`, `utils/`, `settings/` (via AppConfig injection) | Any Layer 1, 3, 4, 5, 6 module directly |

**`permissions/`** is a special case: it implements the user-approval dialogs defined in `09_Security.md`. It may call into `security/` for audit logging but must not import the Presentation layer (CLI) directly. Instead, the Orchestrator provides a `user_prompt` callable at boot time.

### Layer 3 — AI Core

| Module | Allowed Imports | Forbidden Imports |
|---|---|---|
| `llm/` | `utils/`, `security/` (for output sanitisation), its own `ports/` and `providers/` | Any Layer 1, 2, 4+, except via Ports |
| `prompt/` | `utils/`, `settings/` (via AppConfig injection) | Any module outside Layer 3 or cross-cutting |
| `context/` | `utils/`, `security/`, its own `ports/` | Any Layer 4+ module directly (must use MemoryPort) |
| `orchestrator.py` | `utils/`; receives all module references via constructor injection | Direct `import` of any module in `backend/modules/` |

**`orchestrator.py`** is the only module exempt from the layer-adjacency restriction. It is wired to every module through dependency injection. However, it must not directly `import` any module's internal implementation — it only holds references to their public interfaces (typically a single class per module, e.g., `LLMManager`, `ContextManager`).

### Layer 4 — Service

| Module | Allowed Imports | Forbidden Imports |
|---|---|---|
| `voice/` | `utils/`, `pc_control/` (for audio device enumeration), `security/` (for input sanitisation) | Any Layer 1, 2, 3 module |
| `vision/` | `utils/`, `pc_control/` (for screen capture), `memory/` (for caching, not persistence logic) | Any Layer 1, 2, 3 module |
| `browser/` | `utils/`, `security/` (for URL validation) | Any Layer 1, 2, 3 module |
| `file_manager/` | `utils/`, `pc_control/` (for path resolution), `security/` (for sandbox checks) | Any Layer 1, 2, 3 module |

Service modules are heavy execution engines. They may call lower layers directly. They may NOT call upward into AI Core or Application layers.

### Layer 5 — Infrastructure

| Module | Allowed Imports | Forbidden Imports |
|---|---|---|
| `memory/` | `utils/`, `pc_control/` (for file path resolution), its own `adapters/` | Any Layer 1-4 module; any Layer 6 module outside `pc_control/` |

`memory/` contains the SQLite client and the JSON vector index. It exposes adapters that implement Ports defined in higher layers.

### Layer 6 — OS

| Module | Allowed Imports | Forbidden Imports |
|---|---|---|
| `pc_control/` | `utils/` only | Any module outside Layer 6 or cross-cutting |

`pc_control/` directly wraps Windows OS APIs (`pyautogui`, `subprocess`, ctypes). It must be kept maximally isolated so that it can be tested and secured independently.

### Cross-Cutting

| Module | Allowed Imports | Forbidden Imports |
|---|---|---|
| `security/` | `utils/` only, Python stdlib only | Any `backend/` module |
| `utils/` | Python stdlib only, third-party packages listed in `requirements.txt` | Any `backend/` module |

These modules provide services to all layers but must never depend on any `backend/` code.

---

## 4. Module Isolation Rule

**Sibling modules within the same layer must not import each other.**

For example:
- `voice/` must not import `vision/` (both Layer 4).
- `llm/` must not import `prompt/` or `context/` (all Layer 3).
- `browser/` must not import `file_manager/` (both Layer 4).

If two sibling modules need to exchange data, they must do so through the Orchestrator. The Orchestrator orchestrates the data flow; modules never call each other.

**Exception:** Modules within the same sub-package may import each other. For example:
- `llm/providers/gemini.py` may import `llm/llm_port.py`.
- `memory/adapters/sqlite_adapter.py` may import `context/ports/memory_port.py` (this is the Adapter implementing a Port, which is explicitly allowed).

---

## 5. Plugin API Contract (for future Phase 6)

When the Plugin Manager is implemented in Phase 6, external plugins must conform to this contract:

1. A plugin is a Python package installed at a known path (or via pip).
2. It exposes a class implementing `PluginInterface` (defined in `backend/modules/plugin/ports/plugin_port.py`).
3. A plugin belongs to exactly one layer. It must follow the dependency rules of that layer.
4. A plugin receives dependencies through its constructor (injected by the Plugin Manager).
5. A plugin must not import any internal module of Naira-OS directly. It may only import:
   - The `PluginInterface` port.
   - Cross-cutting modules (`utils/`, `security/`).
   - The layer below it (via Ports where applicable).
   - Standard library and third-party packages.
6. A plugin registers its capabilities through the Capability Manager (via the Orchestrator), not by modifying any Naira-OS source code.

---

## 6. Forbidden Patterns

The following patterns are explicitly forbidden and must be caught in code review:

| Pattern | Example | Why |
|---|---|---|
| Direct import across layer boundary skipping a layer | `from backend.modules.pc_control import ...` inside `llm/` | Violates the adjacency rule |
| Sibling import | `from backend.modules.voice import ...` inside `backend/modules/vision/` | Violates module isolation |
| Importing adapter from consumer code | `from backend.modules.memory.adapters.sqlite_adapter import ...` inside `context/` | Bypasses the Port abstraction |
| Importing a higher layer | Any `import` of a lower-numbered layer from a higher-numbered layer | Violates the downward-only rule |
| Cross-cutting importing backend code | `from backend.modules.llm import ...` inside `utils/` or `security/` | Cross-cutting modules must be self-contained |
| `from orchestrator import ...` inside any module | Importing `orchestrator.py` directly from a module | The Orchestrator injects itself via constructor; modules must not reach for it through imports |
| Global mutable state shared between modules | A shared `dict` or `list` in `backend/__init__.py` that multiple modules write to | Creates implicit coupling; makes testing and reasoning impossible |

---

## 7. Enforcement

These rules are enforced through:
1. **Code review:** Every pull request must verify that new imports conform to this document.
2. **Linting (future):** A custom `ruff` plugin or `import-linter` configuration will codify the layer rules once the module structure is stabilised.

---

## 8. Summary Diagram

```
 Cross-cutting: security/, utils/  ← available to all layers, import nothing from backend/
 ─────────────────────────────────────────────────────────────────────

 1. PRESENTATION    avatar/ ──────────▶  may import Layer 2 only
                                        may NOT import Layer 3-6 directly
 2. APPLICATION     capability/, session/, plugin/, settings/, permissions/, ──▶  may import Layer 3 only
                    telemetry/, update/                                         may NOT import Layer 4-6 directly
 3. AI CORE         orchestrator.py, llm/, prompt/, context/
                        │
                        │ (via Ports only)
                        ▼
 4. SERVICE          voice/, vision/, browser/, file_manager/ ──▶  may import Layer 5, 6
 5. INFRASTRUCTURE   memory/ ──▶  may import Layer 6
 6. OS               pc_control/ ──▶  may import utils/ only
```

No arrow points upward. Any code that introduces an upward import is rejected.
