# NAIRALLM COGNITIVE PROTOCOL & TRAINING SPECIFICATION
**Project**: Naira OS AI Assistant Model (NairaLLM)  
**Status**: APPROVED & LOCKED  
**Token Version**: v1.0.0-final  
**Vocab Size**: 4,096 tokens

---

## 1. The 11-Stage Cognitive Pipeline

NairaLLM operates on a deterministic, structured cognitive pipeline from user ingestion to final proactive execution:

```
[USER INPUT] 
     │
     ▼
[<|context|>] ────── Active window, time, clipboard, system load, autonomy level (0-5)
     │
     ▼
[<|intent|>] ────── Classification: category, requires_tool (true/false), risk level
     │
     ├───────────────────────────────────────────┐
     │ requires_tool: true                       │ requires_tool: false
     ▼                                           ▼
[<|plan|>] ──────── Multi-step decomposition    [<|no_tool|>] ─ Direct conversational answer
     │                                           │
     ▼                                           ▼
[<|tool_call|>] ─── JSON invocation            [<|final|>] ──── Direct answer in En/Hi/Hinglish
     │                                           │
     ▼                                           ▼
[<|tool_result|>] ─ Injected environment output [<|proactive|>] Optional event triggers
     │
     ▼
[<|verify|>] ────── Inspection of tool outcome
     │
     ├───────────────────────────────────────────┐
     │ Tool success                              │ Tool error / timeout
     ▼                                           ▼
[<|final|>] ─────── Formatted user response     [<|recover|>] ─ Fallback strategy & alternative tool
     │
     ▼
[<|proactive|>] ─── Autonomous event trigger / next step
```

---

## 2. Standardized Special Tokens (17 Tokens)

| ID | Token | Role | Loss Masking Target | Description |
| :--- | :--- | :--- | :--- | :--- |
| `0` | `<|pad|>` | Padding | **Masked (-100)** | Sequence padding for micro-batch alignment |
| `1` | `<|endoftext|>` | EOS | **Trained** | End of turn generation |
| `2` | `<|system|>` | Header | **Masked (-100)** | System instruction prompt boundary |
| `3` | `<|user|>` | Header | **Masked (-100)** | User prompt boundary |
| `4` | `<|assistant|>` | Header | **Masked (-100)** | Assistant response boundary start |
| `5` | `<|context|>` | Environment | **Masked (-100)** | Injected OS state (`active_window`, `time`, `autonomy_level`) |
| `6` | `<|intent|>` | Cognitive | **Trained** | Structured JSON intent & tool necessity tag |
| `7` | `<|plan|>` | Cognitive | **Trained** | Ordered step-by-step reasoning plan |
| `8` | `<|tool_call|>` | Execution | **Trained** | Strict JSON tool invocation: `{"name": "...", "arguments": {...}}` |
| `9` | `<|tool_result|>` | Observation | **Masked (-100)** | Environment observation injected by OS runtime |
| `10`| `<|verify|>` | Cognitive | **Trained** | Verification check confirming tool result validity |
| `11`| `<|recover|>` | Cognitive | **Trained** | Error recovery / fallback reasoning upon tool error |
| `12`| `<|no_tool|>` | Decision | **Trained** | Explicit marker declaring direct conversational/math response |
| `13`| `<|proactive|>` | Autonomy | **Trained** | Background autonomous event suggestions / state updates |
| `14`| `<|final|>` | Generation | **Trained** | User-facing answer in requested language (En, Hi, Hinglish) |
| `15`| `<|thought|>` | Cognitive | **Trained** | Internal scratchpad reasoning |
| `16`| `<|unk|>` | Fallback | **Masked (-100)** | Unknown token representation |

---

## 3. Strict Target Loss Masking Policy

During training, cross-entropy loss is **strictly computed on model-generated tokens only**:
1. All tokens preceding `<|assistant|>` (`<|system|> ...`, `<|user|> ...`, `<|context|> ...`) receive target label `-100`.
2. All injected environment observations following `<|tool_result|>` up to the next assistant tag receive target label `-100`.
3. Loss is active **only** on cognitive tags: `<|intent|>`, `<|plan|>`, `<|tool_call|>`, `<|verify|>`, `<|recover|>`, `<|no_tool|>`, `<|proactive|>`, `<|final|>`, and `<|endoftext|>`.

This guarantees that the model learns pure causal generation of reasoning, tool schemas, and multilingual dialogue without penalizing the prediction of external user prompts or OS environment outputs.

---

## 4. Structured Output JSON Schemas

### A. Intent Schema
```json
{
  "category": "browser | pc_control | coding | memory | vision | voice | security | conversational",
  "requires_tool": true,
  "summary": "Concise 1-sentence action summary"
}
```

### B. Tool Call Schema
```json
{
  "name": "browser_search",
  "arguments": {
    "query": "transformer model architecture 2026",
    "max_results": 5
  }
}
```

### C. Proactive Autonomy Schema
```json
{
  "action": "suggest_optimization | auto_save_and_standby | defer_notification | silent_queue",
  "target": "parser.py",
  "autonomy_level": 3
}
```
