# NairaLLM Final V1 — Stage 0 Pre-Flight Run Manifest

- **Audit Date**: `2026-08-17 15:45:26 UTC`
- **Pre-Flight Verdict**: **`STAGE_0_PREFLIGHT_PASSED`**
- **Git Commit SHA**: `f6db0b1144615a8ce2c538000947d772c3078e12` (Branch: `main`)
- **Canonical Model**: `NairaTransformer` (1,242,880 tied parameters, vocab=1509)
- **Cost Policy**: Free Cloud GPU Only ($0.00)

---

## 1. Cryptographic Hashes & Artifact Verification

| Artifact / Component | Expected / Actual SHA-256 | Status |
| :--- | :--- | :--- |
| **Model Config** (`final_nairallm_v1.json`) | `c6b9895a99de8b832a6cdd847462fb6d70f693318365eae59a7be5ce854a5a7c` | **PASS** |
| **Tokenizer** (`naira_tokenizer.json`) | `71f6f8d70b56b1ceb4de95013fd70193e7080485ddc5abfe875193f3b83b42ad` | **PASS** |
| **Dataset A** (`dataset_a_semantic.jsonl`) | `015b4655bde092005b31195025e96df6e80702e7975f05ebf0c6072c1b29ff8f` | **PASS** |
| **Dataset B** (`dataset_b_all_capabilities.jsonl`) | `93fe24aef07873fa2fb5a76b5a17da775fe6296ba5b3b6e30823f8ab1c289095` | **PASS** |
| **Dataset C** (`dataset_c_behavior.jsonl`) | `aff52170796c80b1ae84ed7f1eb68393b8ef1c9b42869b2de8c8642910e66fc7` | **PASS** |
| **Foundation Checkpoint** (`foundation/`) | `7bc1fb85644e84a0d2d2f3e46509c4aa5ec203949eeec7c130e94e9fe4667b60` | **PASS** |

---

## 2. Dataset Counts & Grounding Verification

| Dataset Pillar | Records | Tokens | Domain Coverage | Subsystem Grounding |
| :--- | :--- | :--- | :--- | :--- |
| **Dataset A (Semantic)** | 337 | 105141 | 39 balanced scientific/systems domains | Foundation linguistic pretraining |
| **Dataset B (Capability)** | 706 | 71280 | Domain (80), Cognition (91), Tools (535) | Real Naira OS schemas (`pc_*`, `browser_*`, `memory_*`, `coding_*`, `vision_*`) |
| **Dataset C (Behavioral)** | 68 | 8911 | All 18 behavioral patterns | Autonomy Levels 0-5, Quiet mode, Inactivity, Safety escalation |

---

## 3. Evaluation Scaffolding Verification

- **Benchmark File**: `NairaLLM/evaluation/benchmarks/final_v1_eval_prompts.json`
- **Unseen Test Cases**: **360 prompts** (20 per section across 18 sections 1 through 18 in En, Hi, Hinglish)
- **Evaluation Mode**: Pure neural autoregressive generation (no mock fallbacks, exact output logging)
- **Benchmark Harness**: `NairaLLM/evaluation/suites/final_v1_benchmark_suite.py`

---

## 4. Checkpoint Chain Verification

```
foundation (SHA: 7bc1fb85644e...) [VALIDATED SEED]
  └── domain      (Dataset B Domain)
        └── cognition   (Dataset B Cognition)
              └── tools       (Dataset B Tools)
                    └── behavior    (Dataset C Behavior)
                          └── final_v1    (FINAL NAIRALLM V1 FREEZE)
```

---

## 5. Next Training Stage (Stage 1 / Stage 2 Launch Command)

Stage 0 Pre-Flight has **PASSED**. All cryptographic hashes and dataset integrity checks are locked.

When launched on Google Colab / Kaggle Free Tesla T4 GPU, execute:

```bash
# Launch Stage 2 (Domain Training) from Foundation Checkpoint:
python NairaLLM/training/scripts/train_final_v1.py \
    --stage domain \
    --config NairaLLM/configs/final_nairallm_v1.json \
    --parent-checkpoint NairaLLM/training/checkpoints/foundation/foundation_checkpoint_metadata.json
```
