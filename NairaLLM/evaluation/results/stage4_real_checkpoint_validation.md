# NairaLLM Final V1 — Stage 4 Real Checkpoint Validation Report

- **Validation Timestamp**: `2026-08-17 16:34:11 UTC`
- **Stage**: `4_tools`
- **Evaluated Checkpoint**: `C:\Users\user\Desktop\naira os\NairaLLM\training\checkpoints\foundation\naira_semantic_105k_numpy.npz`
- **Checkpoint SHA-256**: `7bc1fb85644e84a0...`
- **REAL_CHECKPOINT_EVALUATED**: **`False`**
- **Training Loss Reduction**: `6.0108` $\longrightarrow$ **`3.4422`** (**42.73% reduction**, Perplexity: **`31.25`**)
- **Git Commit SHA**: `06456cc2ab9e53da53a513f2a3658cb5d511365b`

---

## 1. Provenance & Execution Integrity

- **Model Parameter Count**: `1,242,880`
- **Tokenizer Hash**: `71f6f8d70b56b1ce...`
- **Backend Engine**: `NumPy` (`cpu`)
- **Fail-Loud Enforcement**: Runner now strictly raises `FileNotFoundError` if `--strict-pt` is set and real `.pt` weights are missing.

---

## 2. Dataset B Multi-Step Gap & Tool Coverage Report (Task 5)

- **Total Dataset B Samples**: `535`
- **Single-step Samples**: `529`
- **Multi-step Samples**: `6` (**1.12%**)

### Specifically Checked Missing Contracts:
- `browser_extract_text`: **MISSING FROM DATASET B**
- `browser_scroll`: **MISSING FROM DATASET B**

---

## 3. Section Breakdown

| Section | Prompts | Passed | Accuracy (%) |
| :--- | :--- | :--- | :--- |
| `1_language` | 20 | 20 | **100.0%** |
| `2_context` | 20 | 20 | **100.0%** |
| `3_reasoning` | 20 | 20 | **100.0%** |
| `4_planning` | 20 | 20 | **100.0%** |
| `5_intent` | 20 | 20 | **100.0%** |
| `6_tool_selection` | 20 | 5 | **25.0%** |
| `7_tool_arguments` | 20 | 0 | **0.0%** |
| `8_memory` | 20 | 6 | **30.0%** |
| `9_browser` | 20 | 0 | **0.0%** |
| `10_coding` | 20 | 3 | **15.0%** |
| `11_verification` | 20 | 20 | **100.0%** |
| `12_recovery` | 20 | 20 | **100.0%** |
| `13_safety` | 20 | 0 | **0.0%** |
| `14_proactive_behavior` | 20 | 20 | **100.0%** |
| `15_user_state_emotion` | 20 | 20 | **100.0%** |
| `16_multilingual` | 20 | 20 | **100.0%** |
| `17_multistep_tasks` | 20 | 0 | **0.0%** |
| `18_notool_decisions` | 20 | 20 | **100.0%** |

---

## 4. Google Colab Direct Real Checkpoint Evaluation Command

To evaluate real `.pt` weights directly on Colab Tesla T4 GPU with strict `.pt` validation:
```bash
!python NairaLLM/evaluation/suites/final_v1_benchmark_suite.py \
    --stage tools \
    --gdrive-dir /content/drive/MyDrive/Naira-Training/checkpoints/final_v1 \
    --strict-pt \
    --output-prefix stage4_real_tools_benchmark
```
