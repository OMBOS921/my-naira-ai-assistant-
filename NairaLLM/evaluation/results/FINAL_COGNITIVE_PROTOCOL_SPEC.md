# FINAL COGNITIVE PROTOCOL & TRAINING FORMAT SPECIFICATION (MASTER PROMPT 5)
**Project**: Naira OS AI Assistant Model (NairaLLM)  
**Protocol Version**: 5.0.0-final  
**Target Context Length**: 2048 tokens  
**Verdict**: `READY_FOR_MASTER_PROMPT_6 = true`

---

## 1. Canonical Special Control Tokens

All 17 special tokens are canonically registered in the BPE tokenizer (`vocab_size=4096`):

| Token | ID | Purpose & Semantic Role |
| :--- | :--- | :--- |
| `<|pad|>` | `0` | Sequence batch padding |
| `<|endoftext|>` | `1` | End of generation boundary |
| `<|system|>` | `2` | OS assistant instructions & baseline constraints |
| `<|user|>` | `3` | User voice / keyboard input prompt |
| `<|context|>` | `283` | Injected telemetry (active app, screen, autonomy L0-5, time) |
| `<|assistant|>` | `4` | Generation start boundary for Naira |
| `<|intent|>` | `6` | Goal categorization, safety check, tool necessity flag |
| `<|plan|>` | `7` | Step-by-step dependency execution plan |
| `<|tool_call|>` | `8` | Strict JSON invocation `{"name": "...", "arguments": {...}}` |
| `<|tool_result|>`| `9` | Environment return payload injection |
| `<|verify|>` | `10` | Verification & schema validation of returned data |
| `<|recover|>` | `11` | Error handling, fallback selection, and DAG re-planning |
| `<|no_tool|>` | `12` | Explicit declaration of direct conversational answer |
| `<|proactive|>`| `13` | Proactive decision: `{"speak": bool, "urgency": "..."}` |
| `<|final|>` | `14` | Clear, grounded user-facing response |
| `<|thought|>` | `15` | Internal chain-of-thought scratchpad |
| `<|unk|>` | `16` | Unknown token fallback |

---

## 2. Loss Supervision & Target Masking Rules

To prevent the model from memorizing system prompts or hallucinating environment states, strict target masking is enforced during cross-entropy loss computation:

$$\mathcal{L} = -\frac{1}{N} \sum_{t=1}^N \mathbf{1}[y_t \neq -100] \log P(y_t \mid x_{<t})$$

| Token Span in Sequence | Loss Mask Label | Rationale |
| :--- | :--- | :--- |
| `<|system|> ... <|user|> ... <|context|>` | **`-100`** | Prompt input (conditioned on, not generated) |
| `<|tool_result|> ...` | **`-100`** | External environment observation (injected at runtime) |
| `<|intent|> ... <|plan|> ...` | **`token_id`** | Supervised cognitive reasoning |
| `<|tool_call|> ...` | **`token_id`** | Supervised strict JSON tool call syntax |
| `<|verify|> ... <|recover|> ...` | **`token_id`** | Supervised verification & error handling |
| `<|no_tool|> ... <|proactive|> ...`| **`token_id`** | Supervised proactivity and negative decisions |
| `<|final|> ... <|endoftext|>` | **`token_id`** | Supervised user-facing response |

---

## 3. Context Packing & Truncation Hierarchy (2048 Tokens)

```
┌────────────────────────────────────────────────────────────────────────┐
│ Context Window: Max 2048 Tokens                                         │
├────────────────────────────────────────────────────────────────────────┤
│ [IMMUTABLE TIER 1] System Instructions & Constraints (120 tok)        │
│ [IMMUTABLE TIER 2] Active User Prompt + Recent Context (80 tok)        │
│ [DYNAMIC TIER 3] Active Tool Invocations & Verified Results (500 tok)   │
│ [DYNAMIC TIER 4] Screen State & Active Application Telemetry (200 tok) │
│ [DYNAMIC TIER 5] Relevant User Long-Term Memories (200 tok)            │
│ [TRUNCATABLE TIER 6] Multi-Turn History (FIFO evicted on overflow)    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Verification & Protocol Parser Test Suite

All 5 cognitive protocol unit tests passed with 100% precision:
1. **Full Roundtrip & Loss Masking**: **PASSED**
2. **17 Canonical Special Tokens Registered**: **PASSED**
3. **No-Tool Protocol Parser**: **PASSED**
4. **Proactive Decision Tag Parser**: **PASSED**
5. **Multi-Step Error Recovery Parser**: **PASSED**

---

## 5. Gate Status

```
============================================================
FINAL COGNITIVE PROTOCOL VERDICT: READY_FOR_MASTER_PROMPT_6 = true
- Zero model training executed.
- Zero checkpoints created.
- 100% formal schema specification locked for tokenizer, parser, and trainer.
- Ready to proceed to Master Prompt 6 (Benchmark V3 & Strict Rubrics).
============================================================
```
