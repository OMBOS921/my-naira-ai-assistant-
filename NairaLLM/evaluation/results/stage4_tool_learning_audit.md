# NairaLLM Final V1 — Stage 4 Tool Learning Failure Audit Report

- **Audit Timestamp**: `2026-08-17 16:22:31 UTC`
- **Git Commit SHA**: `1276dffe9803138527811a3afe197943ff30f1c6`
- **Audit Status**: **`ROOT_CAUSE_IDENTIFIED`**

---

## Executive Summary

Training loss successfully dropped by 42.73% (6.0108 -> 3.4422, Perplexity 31.25) during Colab GPU training. However, the benchmark validation scripts evaluated the untuned seed foundation weights (naira_semantic_105k_numpy.npz) because binary .pt checkpoints remained exclusively in Google Drive and were not loaded by the evaluation runner on Colab. Dataset B tools, target masking, token supervision, and schema formats are verified 100% correct.

---

## 1. Task 1 — Dataset B Tools Audit

- **Dataset Path**: `NairaLLM/dataset/final/B_naira_capability/dataset_b_tools.jsonl`
- **Total Training Samples**: `535`
- **Languages**: English: `373 (69.7%)`, Hinglish: `110 (20.6%)`, Hindi: `52 (9.7%)`
- **Difficulties**: Basic: `378 (70.7%)`, Intermediate: `157 (29.3%)`
- **Single-step vs Multi-step**: Single-step: `529 (98.9%)`, Multi-step: `6 (1.1%)`
- **Unique Target Tools**: `34`

### Key Tool Families in Dataset:
- `tool_arguments`: 207
- `tool_selection`: 176
- `browser_research`: 56
- `memory`: 52
- `coding_agent`: 32
- `pc_system_settings` / `pc_control`: 157
- `no_tool` / `safety` contrastive: 28

---

## 2. Task 2 — Training Target & Loss Masking Audit

- **Dataset Class**: `MaskedInstructionDataset`
- **Data Collator**: `InstructionDataCollator` (pad_token_id=0, ignore_index=-100)
- **Masking Integrity**: User & System turns are masked with `-100`. Assistant turns (including `<|thought|>`, `<|tool_call|>`, JSON arguments) are **100% supervised**.
- **Supervision Ratio**: 56.6% to 69.8% of tokens per sequence are supervised.
- **Masking Verdict**: **`VERIFIED_CORRECT`**

---

## 3. Task 5 — Benchmark Integrity & Evaluation Pipeline Audit

### Critical Finding: Evaluation Isolation Disconnect
During post-training validation runs (`run_stage3_validation.py` and `run_stage4_validation.py`), the runner initialized `NairaRuntime` with `naira_semantic_105k_numpy.npz` (the untuned foundation seed) because the `.pt` checkpoint was saved in Google Drive and not passed to the local runtime.

Consequently, the benchmark evaluated the foundation seed across all stages, producing a static 65.0% score while actual Colab training loss dropped from 6.0108 down to 3.4422 (Perplexity 31.25).

---

## 4. Root Cause & Recommendations

### Root Causes Identified:
1. **Evaluation Runner Checkpoint Loading**: Validation runner must evaluate the actual trained `.pt` model on Colab GPU.
2. **Dataset Multi-Step Representation**: Multi-step tool chaining currently accounts for only 1.1% of samples.
3. **Missing Tool Schema Overlap**: 2 out of 20 benchmark tools (`browser_extract_text`, `browser_scroll`) are missing from Dataset B.

### Actionable Recommendations:
1. Update benchmark evaluation runner to directly evaluate the trained PyTorch `.pt` model on Colab.
2. Augment Dataset B with multi-step tool workflows and missing browser actions.
3. Proceed to Stage 5 Behavior Training with proper in-notebook PyTorch benchmark evaluation.
