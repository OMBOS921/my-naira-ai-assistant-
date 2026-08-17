# NairaLLM Final V1 — Stage 2 Domain Training Readiness Report

- **Audit Timestamp**: `2026-08-17 14:52:38 UTC`
- **Target Stage**: `Stage 2 (domain)`
- **Readiness Status**: **`APPROVED_FOR_STAGE_2_TRAINING`**
- **Git Commit SHA**: `91e83e8e6d14e5009eb7ff1821870fb78e3b99be`
- **Pre-Flight Verdict**: **`STAGE_0_PREFLIGHT_PASSED`**

---

## 1. Blocker A Resolution — Checkpoint Lineage & Auto-Discovery

**Issue**: `WARNING — Stage 'domain' requires valid parent checkpoint from 'semantic', but none was found.`

- **Root Cause**: `train_final_v1.py` expected an explicit `--parent-checkpoint` argument and had no predecessor auto-discovery mechanism.
- **Fix**: Implemented `find_latest_checkpoint()` in `CheckpointChainManager`. When `--parent-checkpoint` is omitted, Stage 2 automatically locates, validates, and loads the Stage 1 `semantic` checkpoint.
- **Resolved Parent Checkpoint**: `NairaLLM\training\checkpoints\foundation\naira_semantic_105k_numpy.npz`
- **Resolved Parent Metadata**: `NairaLLM\training\checkpoints\foundation\foundation_checkpoint_metadata.json`
- **Strict Failure Invariant**: If the predecessor checkpoint is missing, training raises `RuntimeError` and **aborts immediately**, preventing uninitialized fresh training.

---

## 2. Blocker B Resolution — Variable-Length Dataset Collation & Loss Masking

**Issue**: `RuntimeError: stack expects each tensor to be equal size, but got [118] at entry 0 and [74] at entry 1`

- **Root Cause**: Dataset B contains multi-turn conversations of varying length. PyTorch's default collator threw an exception when stacking unequal 1D tensors.
- **Fix**: Implemented `InstructionDataCollator`:
  1. Dynamically pads inputs to `batch_max_len` using `pad_token_id` (`0`).
  2. Dynamically pads target tokens with `ignore_index=-100`.
  3. PyTorch `F.cross_entropy(..., ignore_index=-100)` ignores padded tokens completely during loss and gradient computation.
  4. Causal attention masks and assistant instruction supervision are 100% preserved.

---

## 3. Dataset B Domain Integrity

- **Dataset File**: `NairaLLM/dataset/final/B_naira_capability/dataset_b_domain.jsonl`
- **Records**: `80`
- **Tokens**: `5713`
- **SHA-256 (LF)**: `c191394b76e884b84fd39f90f1d1fd7eb8e7b428c3be6233e8604fe952144a4a`
- **Status**: Verified pure LF byte-level parity across Windows and Linux.

---

## 4. Test Suite Execution Summary

| Test Function | Component Verified | Result |
| :--- | :--- | :--- |
| `test_variable_length_collation` | Batch padding on [118, 74] tensors | **PASSED** |
| `test_truncation_at_max_seq_len` | Bounding at `max_seq_len` | **PASSED** |
| `test_loss_masking_on_padding` | `ignore_index=-100` zero loss | **PASSED** |
| `test_empty_batch_safeguard` | Empty batch exception handling | **PASSED** |
| `test_stage_2_parent_discovery` | Auto-discovery of semantic checkpoint | **PASSED** |
| `test_stage_2_foundation_fallback_discovery` | Fallback discovery to foundation seed | **PASSED** |

---

## 5. Exact Google Colab Stage 2 Launch Command

On Google Colab Tesla T4 GPU, execute:
```bash
%cd /content/naira os
!git fetch origin main
!git reset --hard origin/main

# Run preflight verification:
!python NairaLLM/training/scripts/stage_0_preflight.py

# Launch Stage 2 (Domain Training):
!python NairaLLM/training/scripts/train_final_v1.py \
    --stage domain \
    --config NairaLLM/configs/final_nairallm_v1.json
```
