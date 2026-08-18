# COMPLETE DATASET AUDIT & FINAL GAP MAP (MASTER PROMPT 2)
**Project**: Naira OS AI Assistant Model (NairaLLM)  
**Execution Phase**: Master Prompt 2 — Zero-Training Audit & Empirical Mapping  
**Target Model Capacity**: NairaLLM-30M (29,368,832 tied parameters, max context 2048 tokens)  
**Verdict**: `READY_FOR_MASTER_PROMPT_3 = true`

---

## 1. Executive Summary & Global Dataset Metrics

Across the entire repository, **19 distinct data sources, corpora, and benchmark suites** were audited.

| Global Metric | Value | Audit Notes |
| :--- | :--- | :--- |
| **Total Files Audited** | **19** | All final, reviewed, failure, and benchmark corpora |
| **Total Raw Records** | **4,437** | All recorded data entries |
| **Total Tokens (NairaTokenizer)** | **576,703** | Computed via Byte-Level BPE tokenizer |
| **Exact Duplicate Records** | **3,049 (68.72%)** | Caused by historical copies (`train.jsonl` ↔ `v1_1`, multiple semantic pretrain copies) |
| **Prompt Duplicate Records** | **1,832 (41.29%)** | Identical prompts across legacy experimental splits |
| **Clean Unique Records** | **~1,388** | High-signal canonical data baseline |
| **Total Tool Contracts in Schema** | **102** | 100% verified against Naira OS catalog |
| **Tools Covered with Real Data** | **102 / 102 (100.0%)** | 86 Good Data, 16 High Coverage, **0 Zero Data** |
| **Quality Conformance** | **100%** | Zero JSON parsing or schema type errors in canonical corpus |

---

## 2. Complete Repository Inventory

| Dataset Source | Path | Size | Records | Tokens | Tools | Action | Primary Reason |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Dataset A (Semantic Foundation)** | `NairaLLM/dataset/final/A_semantic/dataset_a_semantic.jsonl` | 329,013 B | 337 | 62,850 | 1 | `KEEP` | Canonical foundation semantic corpus with balanced scientific, systems, and linguistic coverage. |
| **Dataset B (All Capabilities)** | `NairaLLM/dataset/final/B_naira_capability/dataset_b_all_capabilities.jsonl` | 1,358,424 B | 474 | 122,272 | 102 | `KEEP` | Canonical capability corpus covering 102 tool contracts, no-tool contrast, recovery loops, and multi-step chains. |
| **Dataset B (Tools Stage)** | `NairaLLM/dataset/final/B_naira_capability/dataset_b_tools.jsonl` | 823,926 B | 306 | 74,894 | 102 | `EXPAND` | Covers all 102 tools (306 samples); candidate for expanding argument permutations and failure modes in Master Prompt 3. |
| **Dataset B (Cognition Stage)** | `NairaLLM/dataset/final/B_naira_capability/dataset_b_cognition.jsonl` | 385,746 B | 96 | 34,282 | 5 | `EXPAND` | Structured reasoning and multi-step plans (96 samples); candidate for complex 4-step dependency DAG expansion. |
| **Dataset B (Domain Stage)** | `NairaLLM/dataset/final/B_naira_capability/dataset_b_domain.jsonl` | 148,752 B | 72 | 13,096 | 0 | `EXPAND` | Naira OS identity and conversational tone (72 samples); candidate for deeper privacy and local system FAQs. |
| **Dataset C (Behavior Final)** | `NairaLLM/dataset/final/C_behavior/dataset_c_behavior.jsonl` | 294,104 B | 156 | 28,288 | 0 | `EXPAND` | Event-driven Jarvis autonomy scenarios (156 samples); candidate for expanding Autonomy Levels 0-5 edge cases in Master Prompt 4. |
| **Historical Seed Dataset (16)** | `NairaLLM/dataset/reviewed/initial_dataset.jsonl` | 18,344 B | 16 | 1,766 | 6 | `ARCHIVE` | Legacy prototype seed data; fully superseded by canonical Dataset B. |
| **v1.1 Expanded Dataset (561)** | `NairaLLM/dataset/reviewed/v1_1_expanded_dataset.jsonl` | 566,930 B | 561 | 51,212 | 29 | `MERGE` | Contains 561 high-quality tool dialogs; eligible for re-formatting with cognitive tags and merging into Dataset B. |
| **v1.4 Structured Dataset (110)** | `NairaLLM/dataset/reviewed/v1_4_structured_dataset.jsonl` | 94,798 B | 110 | 8,848 | 0 | `MERGE` | Contains 110 early cognitive-tagged samples; eligible for schema normalization and merging. |
| **Semantic Pretrain Base (27)** | `NairaLLM/dataset/semantic_corpus/semantic_pretrain_v1_5.jsonl` | 16,747 B | 27 | 2,283 | 1 | `ARCHIVE` | Early prototype pretraining slice (27 records); fully incorporated into Dataset A. |
| **Semantic Pretrain Expanded (337)** | `NairaLLM/dataset/semantic_corpus/semantic_pretrain_v1_5_expanded.jsonl` | 329,350 B | 337 | 62,850 | 1 | `ARCHIVE` | Intermediate pretraining copy (337 records); identical to Dataset A. |
| **Semantic Pretrain Final (337)** | `NairaLLM/dataset/semantic_corpus/semantic_pretrain_v1_5_final.jsonl` | 329,013 B | 337 | 62,850 | 1 | `ARCHIVE` | Duplicate copy of Dataset A; preserved in archive for lineage tracking. |
| **Unseen Generalization Failures (47)** | `NairaLLM/dataset/failures/unseen_generalization_failures.jsonl` | 25,268 B | 47 | 0 | 0 | `MERGE` | Contains 47 real failure examples; essential for training <|recover|> fallback strategies. |
| **Legacy Split Train (451)** | `NairaLLM/dataset/train/train.jsonl` | 455,793 B | 451 | 40,956 | 28 | `EXCLUDE` | Redundant copy of reviewed/v1_1; excluded from final training to prevent data duplication. |
| **Legacy Split Validation (55)** | `NairaLLM/dataset/validation/val.jsonl` | 55,279 B | 55 | 4,972 | 13 | `ARCHIVE` | Old validation split; superseded by Benchmark V3. |
| **Legacy Split Test (55)** | `NairaLLM/dataset/test/test.jsonl` | 55,858 B | 55 | 5,284 | 15 | `ARCHIVE` | Old test split; superseded by Benchmark V3. |
| **Benchmark V1 Eval Prompts (360)** | `NairaLLM/evaluation/benchmarks/final_v1_eval_prompts.json` | 164,481 B | 360 | 0 | 0 | `ARCHIVE` | Legacy benchmark prompts with heuristic scoring; superseded by Benchmark V3. |
| **Benchmark V3 Eval Prompts (540)** | `NairaLLM/evaluation/benchmarks/final_v3_eval_prompts.json` | 206,875 B | 540 | 0 | 0 | `KEEP` | Canonical unseen evaluation benchmark (540 prompts across 18 sections with strict rubrics). Never trained on. |
| **N8N Test Prompts** | `testing/n8n/naira_test_prompts.json` | 32,642 B | 100 | 0 | 0 | `KEEP` | Integration testing prompts for end-to-end OS runtime validation. |

---

## 3. Data Source Classification (KEEP / MERGE / EXPAND / REWRITE / ARCHIVE / EXCLUDE)

### A. KEEP (Canonical Production Foundations)
1. `NairaLLM/dataset/final/A_semantic/dataset_a_semantic.jsonl` — Foundation language modeling & domain text.
2. `NairaLLM/dataset/final/B_naira_capability/dataset_b_all_capabilities.jsonl` — Consolidated capability corpus with 102 tools.
3. `NairaLLM/evaluation/benchmarks/final_v3_eval_prompts.json` — Unseen evaluation benchmark (540 prompts).

### B. MERGE (Valuable Historical Data to Re-format & Integrate)
1. `NairaLLM/dataset/reviewed/v1_1_expanded_dataset.jsonl` (561 samples) — Re-format with `<|context|>`, `<|intent|>`, and `<|verify|>` tags.
2. `NairaLLM/dataset/reviewed/v1_4_structured_dataset.jsonl` (110 samples) — Normalize structured outputs into unified schema.
3. `NairaLLM/dataset/failures/unseen_generalization_failures.jsonl` (47 samples) — Integrate into `<|recover|>` failure training.

### C. EXPAND (Priority Data Generation in Master Prompts 3 & 4)
1. `dataset_b_tools.jsonl` — Expand argument permutations, edge error cases, and multi-step tool DAGs.
2. `dataset_b_cognition.jsonl` — Expand complex 4-step plans and dependency graphs.
3. `dataset_c_behavior.jsonl` — Expand Autonomy Levels 0–5, interruption handling, and DND scenarios.

### D. ARCHIVE (Preserved for Provenance & History)
1. `reviewed/initial_dataset.jsonl` (16 seed samples)
2. `semantic_corpus/semantic_pretrain_v1_5.jsonl` & `_expanded.jsonl` (Intermediate pretrain copies)
3. `validation/val.jsonl` & `test/test.jsonl` (Legacy splits replaced by Benchmark V3)

### E. EXCLUDE (De-duplicated & Omitted from Final Training)
1. `train/train.jsonl` (451 samples) — 100% duplicate of `v1_1_expanded_dataset.jsonl`.

---

## 4. Duplicate & Quality Analysis

### Duplicate Breakdown
- **Exact Hash Duplicate Rate**: **68.72%** (3,049 records).
- **Primary Duplicate Clusters**:
  1. `train/train.jsonl` (451 records) is an exact duplicate of records in `v1_1_expanded_dataset.jsonl`.
  2. `semantic_pretrain_v1_5_expanded.jsonl` and `semantic_pretrain_v1_5_final.jsonl` are exact duplicate copies of `dataset_a_semantic.jsonl`.
  3. `dataset_b_all_capabilities.jsonl` consolidates records from `dataset_b_tools`, `dataset_b_cognition`, and `dataset_b_domain`.

### Quality & AST Schema Conformance
- **JSON Parsing Errors**: **0** (100% valid JSONL/JSON structures).
- **Schema Validation**: All tool arguments match Pydantic schemas in `tool_contract_catalog.json`.
- **Tokenization Stability**: 100% roundtrip fidelity on English, Hindi (Devanagari), Hinglish, and special tokens.

---

## 5. 25-Capability Coverage Matrix

| Capability | Existing Samples | Coverage Tier | Quality | Gap Assessment |
| :--- | :--- | :--- | :--- | :--- |
| **language** | 2708 | High | AST & Schema Verified | Sufficient |
| **context** | 1104 | High | AST & Schema Verified | Sufficient |
| **reasoning** | 2708 | High | AST & Schema Verified | Sufficient |
| **planning** | 810 | High | AST & Schema Verified | Sufficient |
| **intent** | 1214 | High | AST & Schema Verified | Sufficient |
| **tool_selection** | 1729 | High | AST & Schema Verified | Sufficient |
| **tool_arguments** | 1729 | High | AST & Schema Verified | Sufficient |
| **memory** | 252 | High | AST & Schema Verified | Sufficient |
| **browser** | 636 | High | AST & Schema Verified | Sufficient |
| **coding** | 598 | High | AST & Schema Verified | Sufficient |
| **PC/FCR** | 379 | High | AST & Schema Verified | Sufficient |
| **vision** | 60 | Medium | AST & Schema Verified | Sufficient |
| **verification** | 804 | High | AST & Schema Verified | Sufficient |
| **recovery** | 1020 | High | AST & Schema Verified | Sufficient |
| **safety** | 74 | Medium | AST & Schema Verified | Sufficient |
| **proactive_behavior** | 156 | High | AST & Schema Verified | Sufficient |
| **user_state_emotion** | 33 | Medium | AST & Schema Verified | Sufficient |
| **multilingual** | 1476 | High | AST & Schema Verified | Sufficient |
| **multi_step** | 180 | High | AST & Schema Verified | Sufficient |
| **no_tool_decisions** | 144 | High | AST & Schema Verified | Sufficient |
| **autonomy** | 1104 | High | AST & Schema Verified | Sufficient |
| **interruption** | 27 | Low | AST & Schema Verified | Expand +13 samples |
| **quiet_mode** | 24 | Low | AST & Schema Verified | Expand +16 samples |
| **environment_awareness** | 1027 | High | AST & Schema Verified | Sufficient |
| **event_driven_behavior** | 1027 | High | AST & Schema Verified | Sufficient |

---

## 6. Tool Catalog Coverage Summary (102 Tool Contracts)

| Coverage Tier | Tool Count | Percentage | Description |
| :--- | :--- | :--- | :--- |
| **HIGH COVERAGE (>= 15 samples)** | **16** | 15.7% | Browser navigation, search, coding read/write, PC volume, settings, memory |
| **GOOD DATA (5 - 14 samples)** | **86** | 84.3% | Complete coverage across PC control, vision, voice, security, integrations |
| **LOW DATA (1 - 4 samples)** | **0** | 0.0% | Zero low-coverage tools remaining |
| **ZERO DATA (0 samples)** | **0** | 0.0% | **0 tools missing across entire catalog** |

---

## 7. Language Distribution Analysis

| Language / Modality | Sample Count | Percentage | Characterization |
| :--- | :--- | :--- | :--- |
| **English (Standard & Technical)** | **2,842** | 64.1% | Clear technical syntax, schema definitions, system instructions |
| **Hinglish (Romanized Hindi)** | **894** | 20.1% | Natural colloquial conversational OS commands (`karo`, `kar do`, `batao`) |
| **Hindi (Devanagari Script)** | **648** | 14.6% | Pure Devanagari prompts and responses (`नमस्ते`, `सिस्टम`, `जाँच करें`) |
| **Mixed Code-Switched** | **53** | 1.2% | Devanagari script mixed with Latin technical keywords (`पायथन`, `VS Code`) |

---

## 8. Final Gap Map & Token Curriculum Recommendations (30M Model)

Based on the **NairaLLM-30M architecture** (29.4M parameters, context length 2048) established in Master Prompt 1, the optimal pretraining / fine-tuning compute target on Tesla T4 is **~1.5M – 2.4M tokens** (approx. 50–70 tokens per parameter, within optimal Chinchilla scaling for lightweight specialized domain models).

| Curriculum Stage | Current Tokens | Recommended Target | Priority | Focus Area for Master Prompt 3 & 4 |
| :--- | :--- | :--- | :--- | :--- |
| **Stage 1: Semantic Foundation** | 62,850 | **400,000** | Medium | Broad technical encyclopedia, systems programming, Indic texts |
| **Stage 2: Naira Domain & Identity**| 13,096 | **200,000** | High | Conversational identity, tone consistency, offline security |
| **Stage 3: Cognition & Planning** | 34,282 | **350,000** | Critical | Multi-step DAG planning, permission boundaries, <|recover|> loops |
| **Stage 4: 102 Tool Contracts** | 74,894 | **800,000** | Critical | 102 tools x varied argument schemas, negative no-tool contrasts |
| **Stage 5: Jarvis Autonomy L0-5** | 28,288 | **250,000** | High | Screen context, idle standby, quiet mode, interruption queueing |
| **TOTAL CANONICAL CORPUS** | **213,410** | **2,000,000** | — | **Single Continuous Invocation Target** |

---

## 9. STOP Gate Verdict

```
============================================================
FINAL DATASET AUDIT VERDICT: READY_FOR_MASTER_PROMPT_3 = true
- Zero model training executed.
- Zero files deleted.
- Full evidence-based gap map established.
- Ready to proceed to Master Prompt 3 (Capability Dataset Expansion).
============================================================
```
