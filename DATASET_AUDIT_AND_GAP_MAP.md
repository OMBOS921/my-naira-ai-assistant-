# COMPLETE DATASET AUDIT & GAP MAP
**Project**: Naira OS AI Assistant Model (NairaLLM)  
**Status**: AUDIT COMPLETE — CANONICAL MAPPING LOCKED  
**Policy**: Zero File Deletions. Strict Canonical Lineage Mapping.

---

## 1. Executive Inventory

A comprehensive audit was performed across all legacy, reviewed, generator-produced, and staged dataset files in the repository.

| Dataset File | Size (Bytes) | Samples | Primary Family | SHA-256 Hash Prefix |
| :--- | :--- | :--- | :--- | :--- |
| `NairaLLM/dataset/final/A_semantic/dataset_a_semantic.jsonl` | 329,013 | 337 | Foundation Semantic | `015b4655bde0` |
| `NairaLLM/dataset/final/B_naira_capability/dataset_b_all_capabilities.jsonl` | 739,258 | 706 | Capabilities (Multi) | `93fe24aef078` |
| `NairaLLM/dataset/final/B_naira_capability/dataset_b_domain.jsonl` | 65,863 | 80 | Naira Domain Tone | `c191394b76e8` |
| `NairaLLM/dataset/final/B_naira_capability/dataset_b_cognition.jsonl` | 104,045 | 91 | Structured Cognition | `4a8e8de37c59` |
| `NairaLLM/dataset/final/B_naira_capability/dataset_b_tools.jsonl` | 569,350 | 535 | OS Tool Calling | `583d88d0d2e2` |
| `NairaLLM/dataset/final/C_behavior/dataset_c_behavior.jsonl` | 54,280 | 68 | Jarvis Autonomy | `aff52170796c` |
| `NairaLLM/dataset/reviewed/initial_dataset.jsonl` | 18,344 | 16 | Seed Dialogs | `31a391a66b09` |
| `NairaLLM/dataset/reviewed/v1_1_expanded_dataset.jsonl` | 566,930 | 561 | Legacy Tool Calling | `dd77372fa311` |
| `NairaLLM/dataset/reviewed/v1_4_structured_dataset.jsonl` | 94,798 | 110 | Early Tagged Cognition | `5fa723f00b50` |
| `NairaLLM/dataset/semantic_corpus/semantic_pretrain_v1_5_final.jsonl` | 329,013 | 337 | Pretrain Foundation | `015b4655bde0` |
| `NairaLLM/dataset/failures/unseen_generalization_failures.jsonl` | 25,268 | 47 | Error Recovery Seeds | `08a52bfb2240` |
| `NairaLLM/dataset/train/train.jsonl` | 455,793 | 451 | Split Train | `440c1eb7a494` |
| `NairaLLM/dataset/validation/val.jsonl` | 55,279 | 55 | Split Validation | `8a065011d251` |
| `NairaLLM/dataset/test/test.jsonl` | 55,858 | 55 | Split Test | `44bbaace0911` |
| `NairaLLM/dataset/schemas/tool_contract_catalog.json` | 67,120 | 102 | Canonical Schemas | `c06fa9bed8ff` |

---

## 2. Six-Dimensional Gap Analysis

```
  ┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
  │     USEFUL      │       │    DUPLICATE    │       │      WEAK       │
  │ • Real Schemas  │       │ • train.jsonl ↔ │       │ • Len>0 / Len>5 │
  │ • Hi/Hinglish   │       │   v1_1 dataset  │       │ • Missing tags  │
  │ • 40 Generators │       │ • Semantic dups │       │ • Single-turn   │
  └────────┬────────┘       └────────┬────────┘       └────────┬────────┘
           │                         │                         │
  ┌────────┴─────────────────────────┴─────────────────────────┴────────┐
  │                                                                     │
  │                   CANONICAL CORPUS INTEGRATION                      │
  │                                                                     │
  └────────┬─────────────────────────┬─────────────────────────┬────────┘
           │                         │                         │
  ┌────────┴────────┐       ┌────────┴────────┐       ┌────────┴────────┐
  │     MISSING     │       │    OUTDATED     │       │ CANONICAL FINAL │
  │ • 70/102 tools  │       │ • Untagged user │       │ • Dataset A     │
  │ • No-tool cases │       │ • Old API types │       │ • Dataset B     │
  │ • Autonomy L0-5 │       │ • Free-form JSON│       │ • Dataset C     │
  └─────────────────┘       └─────────────────┘       └─────────────────┘
```

### 1. What is Useful (Retained & Incorporated)
- **Tool Contract Schema**: `NairaLLM/dataset/schemas/tool_contract_catalog.json` containing exact JSON schemas for all 102 tools.
- **Linguistic Breadth**: 40 domain generators in `NairaLLM/dataset/generators/` producing rich Hindi Devanagari, Hinglish, systems engineering, and computational concepts.
- **Failure Corpus**: `failures/unseen_generalization_failures.jsonl` (47 samples) providing foundational negative examples for tool error recovery.

### 2. What is Duplicate (De-duplicated in Canonical Corpus)
- `train/train.jsonl` (451 samples) is an uncurated duplicate of records from `v1_1_expanded_dataset.jsonl`.
- `semantic_pretrain_v1_5_expanded.jsonl` and `semantic_pretrain_v1_5_final.jsonl` have 100% duplicate content with `dataset_a_semantic.jsonl`.

### 3. What is Weak (Replaced / Augmented)
- Historical samples with single-line completions lacking `<|context|>`, `<|intent|>`, and `<|verify|>` tags.
- Historical benchmark heuristics that rewarded `len > 5` or keyword presence instead of schema-conformant JSON arguments.

### 4. What is Missing (Identified Gaps to Solve in Dataset B & C)
1. **Tool Coverage Gap**: The legacy dataset covered only 32 out of 102 tools; **70 tools were completely missing** (e.g. browser cookies/PDF/JS, vision face/OCR/UI, coding pipeline/skills, voice synthesis/transcription).
2. **No-Tool Decision Contrast**: No explicit negative samples where the user asks general or mathematical questions and the assistant correctly refuses to invoke an unnecessary tool.
3. **Multi-Step Tool Chaining**: Sequences of 3+ consecutive actions (e.g. `browser_navigate` $\to$ `browser_extract_text` $\to$ `coding_agent_write_file` $\to$ `execute_command`).
4. **Tool Error Recovery Loops**: Explicit sequences where a tool fails (`<|tool_result|> {"error": "404 Not Found"}`), triggering `<|recover|>` and an alternate fallback tool.
5. **Autonomy Level Boundary Cases (L0–L5)**: Scenarios demonstrating bounded execution vs requiring user confirmation for destructive commands (e.g. filesystem wipe, account token export).

### 5. What is Outdated (Modernized)
- Early prompt formats using raw untagged plaintext without target loss masking.
- Deprecated tool names from legacy prototype iterations.

### 6. Canonical Final Corpus Plan
The canonical dataset structure strictly defines 3 non-overlapping, high-density files:
- **Dataset A (`A_semantic/dataset_a_semantic.jsonl`)**: Foundation language modeling and science/systems knowledge (337 samples, ~105k tokens).
- **Dataset B (`B_naira_capability/`)**: Complete capability dataset covering all 102 tool contracts, no-tool contrasts, multi-step execution, and error recovery (~800+ samples, ~150k tokens).
- **Dataset C (`C_behavior/dataset_c_behavior.jsonl`)**: Event-driven Jarvis behavior, interruption handling, quiet mode, and autonomy levels 0–5 (150+ samples, ~40k tokens).
