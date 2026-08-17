# Real Naira OS Subsystem Interfaces and System Contracts

This document records the verified interfaces of the parent Naira OS repository based directly on source code inspection. NairaLLM uses these exact interfaces for tool definition, argument serialization, tool execution, memory interaction, browser research, coding agent handoff, and proactive behaviors.

---

## 1. Core Types (`backend/types.py`)

- **`ToolCall`**:
  ```python
  @dataclass(frozen=True)
  class ToolCall:
      id: str
      name: str
      arguments: dict[str, Any]
  ```
- **`ToolDef`**:
  ```python
  @dataclass(frozen=True)
  class ToolDef:
      name: str
      description: str
      parameters: dict[str, Any]  # JSON Schema
  ```
- **`ToolResult`**:
  ```python
  @dataclass(frozen=True)
  class ToolResult:
      status: Literal["success", "error", "timeout"]
      output: str | None = None
      error: str | None = None
      audio_bytes: bytes | None = None
  ```
- **`Message`**:
  ```python
  @dataclass(frozen=True)
  class Message:
      role: Literal["system", "user", "assistant", "tool"]
      content: str
      tool_calls: list[ToolCall] | None = None
      tool_call_id: str | None = None
  ```
- **`UserRequest`** & **`UserResponse`**: Inbound/outbound lifecycle message contracts.
- **`ModuleInterface`**: Protocol with `async def async_init(self)`, `async def async_shutdown(self)`, and `def degrade(self)`.

---

## 2. Tool Subsystem (`backend/modules/tools/tools_module.py`)

- **`ToolManager`**:
  - `async def execute_tool_call(self, tool_call: ToolCall, context: dict[str, Any] | None = None) -> ToolResult`
  - `async def execute(self, name: str, arguments: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult`
  - `async def execute_multi(self, tool_calls: list[ToolCall], context: dict[str, Any] | None = None) -> list[ToolResult]`
  - `def get_tool_defs(self, category: str | None = None) -> list[ToolDef]`

---

## 3. Memory Subsystem (`backend/modules/memory/memory_module.py`)

- **Built-in Memory Tools**:
  - `remember_fact`: `{"topic": str, "fact": str}`
  - `search_memory`: `{"query": str, "search_type": "all"|"conversations"|"timeline"|"semantic"|"profile", "limit": int}`
- **`MemoryManager` Core Methods**:
  - `async def get_context_block(self, session_id: str) -> str`
  - `async def record_message_memory(self, message: str, role: str, session_id: str) -> None`
  - `async def record_event(...) -> int | None`
  - `async def upsert_knowledge(self, subject: str, predicate: str, object_: str, ...) -> bool`
  - `async def set_user_profile(self, key: str, value: object, ...) -> bool`

---

## 4. Browser Subsystem (`backend/modules/browser/browser_module.py`)

- **Browser Tools**:
  - `browser_search`: `{"query": str, "max_results": int}`
  - `browser_navigate`: `{"url": str, "timeout": float}`
  - `browser_extract_text`: `{"selector": str | None, "timeout": float}`
  - `browser_click`: `{"selector": str, "timeout": float}`
  - `browser_fill`: `{"selector": str, "text": str, "timeout": float}`
  - `browser_screenshot`: `{"url": str | None, "save_path": str | None, "timeout": float}`
  - `browser_new_tab`: `{"url": str | None}`
  - `browser_close_tab`: `{"tab_id": str}`
  - `browser_list_tabs`: `{}`
  - `browser_switch_tab`: `{"tab_id": str}`

---

## 5. Coding Subsystem (`backend/modules/coding_agent/coding_agent_module.py`)

- **`CodingAgentManager`**:
  - Acts as the deterministic execution engine for code analysis, patch generation, git operations, testing, and skill packs (e.g. `python_expert`, `fastapi_expert`, `react_expert`).
  - **NairaLLM role**: High-level reasoning, requirement understanding, architecture planning, and cognitive delegation to the coding agent.

---

## 6. PC Control Subsystem (`backend/modules/pc_control/pc_control_module.py`)

- **PC Control Tools**:
  - `pc_mouse`: `{"action": "move_to"|"click"|"double_click"|"right_click"|"drag"|"scroll"|"get_position", "x": int, "y": int}`
  - `pc_keyboard`: `{"action": "type_text"|"press_key"|"hotkey", "text": str, "key": str, "keys": list[str]}`
  - `pc_clipboard`: `{"action": "get_text"|"set_text"|"clear", "text": str}`
  - `pc_window`: `{"action": "list"|"focus"|"minimize"|"maximize"|"close", "title": str}`
  - `pc_application`: `{"action": "launch"|"close", "app_name": str}`
  - `pc_system_settings`: `{"setting": "volume"|"brightness", "value": int}`

---

## 7. Planning Subsystem (`backend/modules/planning/_types.py`)

- **`TaskStep`**:
  ```python
  @dataclass
  class TaskStep:
      id: str
      description: str
      tool_name: str
      tool_args: dict[str, Any] = field(default_factory=dict)
      depends_on: list[str] = field(default_factory=list)
      status: StepStatus = StepStatus.PENDING
  ```
- **`TaskPlan`**: `steps: list[TaskStep]`, `original_request: str`, `plan_id: str`.

---

## 8. Security & Permissions (`backend/modules/security/_types.py`)

- **`RiskLevel`**: `"low"`, `"medium"`, `"high"`, `"critical"`
- **`PermissionMode`**: `"allow"`, `"deny"`, `"confirm"`, `"admin"`
- **`SecurityCheck`**:
  ```python
  @dataclass(frozen=True)
  class SecurityCheck:
      status: SecurityStatus
      risk_level: RiskLevel = RiskLevel.LOW
      reason: str | None = None
      denied: bool = False
      requires_confirmation: bool = False
      sanitized_input: dict[str, Any] | None = None
  ```

---

## 9. Proactive & Autonomous Policies (`backend/runtime/proactive_watchdog.py`)

- **Autonomy Levels (0–5)**:
  - `Level 0`: Informational (Passive status / logs)
  - `Level 1`: Suggestion (Proactive advice without execution)
  - `Level 2`: Confirmation Required (Ask before executing low-risk action)
  - `Level 3`: Low-Risk Execute (Safe auto-action with notification)
  - `Level 4`: Approved Multi-Step (Autonomous step execution within pre-approved boundary)
  - `Level 5`: Bounded Proactive Automation (Bounded periodic maintenance)
