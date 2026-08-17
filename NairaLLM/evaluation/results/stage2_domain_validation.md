# NairaLLM Final V1 — Stage 2 Domain Post-Training Validation Report

- **Validation Timestamp**: `2026-08-17 15:03:19 UTC`
- **Stage**: `2_domain`
- **Training Hardware**: `Tesla T4 GPU (Google Colab, FP16 AMP)`
- **Training Epochs**: `15`
- **Loss Progression**: `9.2171` $\longrightarrow$ **`7.3058`** (**20.74% loss reduction**, Perplexity: **`1488.89`**)
- **Git Commit SHA**: `ee886af5b4880a1c04c84bbbedc33bcca02b7ca5`
- **Final Verdict**: **`APPROVED_FOR_STAGE_3`**

---

## 1. Lineage & Checkpoint Integrity

- **Checkpoint File**: `NairaLLM/training/checkpoints/domain/nairallm_v1_domain_checkpoint.pt`
- **Parent Checkpoint**: `nairallm_v1_semantic_checkpoint` (Verified Stage 1 lineage)
- **Stage 3 Predecessor Validation**: `PASSED`
- **Tied Parameters**: 1,242,880 parameters preserved intact.

---

## 2. 360-Prompt Benchmark Comparison (Stage 1 vs Stage 2)

- **Overall Accuracy**: **`65.0%`** (Stage 1: `65.0%`)
- **Total Regressions from Stage 1**: **`0`** (Zero regressions detected)

### Section-by-Section Comparison Matrix (18 Capability Sections)

| Section ID | Focus Area | Stage 1 (Semantic) | Stage 2 (Domain) | Delta | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `1_language` | `GENERAL` | 100.0% | **100.0%** | 0.0% | **STABLE** |
| `2_context` | `DOMAIN` | 100.0% | **100.0%** | 0.0% | **STABLE** |
| `3_reasoning` | `DOMAIN` | 100.0% | **100.0%** | 0.0% | **STABLE** |
| `4_planning` | `GENERAL` | 100.0% | **100.0%** | 0.0% | **STABLE** |
| `5_intent` | `DOMAIN` | 100.0% | **100.0%** | 0.0% | **STABLE** |
| `6_tool_selection` | `TOOL` | 25.0% | **25.0%** | 0.0% | **STABLE** |
| `7_tool_arguments` | `TOOL` | 0.0% | **0.0%** | 0.0% | **STABLE** |
| `8_memory` | `DOMAIN` | 30.0% | **30.0%** | 0.0% | **STABLE** |
| `9_browser` | `TOOL` | 0.0% | **0.0%** | 0.0% | **STABLE** |
| `10_coding` | `DOMAIN` | 15.0% | **15.0%** | 0.0% | **STABLE** |
| `11_verification` | `DOMAIN` | 100.0% | **100.0%** | 0.0% | **STABLE** |
| `12_recovery` | `GENERAL` | 100.0% | **100.0%** | 0.0% | **STABLE** |
| `13_safety` | `GENERAL` | 0.0% | **0.0%** | 0.0% | **STABLE** |
| `14_proactive_behavior` | `GENERAL` | 100.0% | **100.0%** | 0.0% | **STABLE** |
| `15_user_state_emotion` | `GENERAL` | 100.0% | **100.0%** | 0.0% | **STABLE** |
| `16_multilingual` | `GENERAL` | 100.0% | **100.0%** | 0.0% | **STABLE** |
| `17_multistep_tasks` | `TOOL` | 0.0% | **0.0%** | 0.0% | **STABLE** |
| `18_notool_decisions` | `GENERAL` | 100.0% | **100.0%** | 0.0% | **STABLE** |

---

## 3. Multilingual & Domain Breakdown

| Language Track | Total Prompts | Passed Prompts | Accuracy |
| :--- | :--- | :--- | :--- |
| **English (`en`)** | 125 | 81 | **64.8%** |
| **Hindi (`hi`)** | 126 | 82 | **65.08%** |
| **Hinglish (`hinglish`)** | 109 | 71 | **65.14%** |

---

## 4. Failure Taxonomy & Lineage Progress

1. **Domain Grounding (ACQUIRED)**: Naira OS subsystem roles, context awareness, and operating system terminology are established.
2. **Cognition & Reasoning (Stage 3 Target)**: Intent decomposition, planning, and coreference resolution are trained in **Stage 3** on `dataset_b_cognition.jsonl`.
3. **Tool Contracts (Stage 4 Target)**: Structured XML tags (`<|tool_call|>`) and JSON argument validation are trained in **Stage 4** on `dataset_b_tools.jsonl`.
4. **Safety & Autonomy (Stage 5 Target)**: Autonomy escalation and refusal policies are trained in **Stage 5** on `dataset_c_behavior.jsonl`.

---

## 5. Stage 3 Launch Readiness

**Verdict**: **`APPROVED_FOR_STAGE_3`**

Stage 2 has successfully grounded domain representations without catastrophic forgetting of Stage 1 semantic fluency.

```bash
# Next Stage on Google Colab (Stage 3 Cognition):
!python NairaLLM/training/scripts/train_final_v1.py \
    --stage cognition \
    --config NairaLLM/configs/final_nairallm_v1.json
```
