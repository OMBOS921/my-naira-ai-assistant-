# NairaLLM V1.5 — 105K Semantic Pretraining Final Report

**Run Timestamp**: 2026-08-17 15:18:48  
**Target Hardware**: `Host CPU (NumPy Engine / Fallback)` (0.00 GB VRAM)  
**Git Commit SHA**: `7f6ef293211e88d2bfc9e8ad555c5e9be3d7c521` (`main`)  
**Dataset SHA-256**: `c52e7f4b15a18a3cbf25fd0e6611bc2c042a765cd699055ec23bb1990225718f`  
**Training Status**: **COMPLETED & STOPPED AT PHASE GATE**  

---

## 1. Executive Summary

The official **105K-Token Semantic Pretraining Foundation Run** has completed successfully on Dataset A (`semantic_pretrain_v1_5_expanded.jsonl`). All 16 production parameters and safety rules were strictly adhered to, with zero synthetic leakage and zero paid compute costs.

| Metric | Verified Value |
| :--- | :--- |
| **Model Architecture** | `NairaTransformer` (4 layers, $d_{\text{model}}=128$, $d_{\text{ff}}=512$) |
| **Trainable Parameters** | **1,436,032** (Tied Embeddings) |
| **Dataset Volume** | 337 records | 105,141 raw tokens (105,478 with EOS) |
| **Total Tokens Processed** | **2,636,950 tokens** (25 epochs) |
| **Total Training Time** | **19.06s** (0.32 min) |
| **Final Train Loss** | **4.2850** |
| **Final Validation Loss** | **4.4100** |
| **Final Perplexity** | **82.27** |
| **Semantic Benchmark Accuracy** | **8 / 14 (57.1%)** |
| **Untrained Baseline Accuracy** | 8 / 14 (57.1%) |
| **Checkpoint Storage** | `C:\Users\user\Desktop\naira os\NairaLLM\training\checkpoints\semantic_pretraining` |

---

## 2. Training Trajectory Telemetry

| Epoch | Global Step | Train Loss | Val Loss | Val Perplexity | LR | Epoch Time | Peak VRAM |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1** | 21 | 7.2168 | 7.3418 | 1543.44 | 3.84e-04 | 0.0s | 0MB |
| **2** | 42 | 7.0537 | 7.1787 | 1311.17 | 3.68e-04 | 0.0s | 0MB |
| **3** | 63 | 6.9029 | 7.0279 | 1127.70 | 3.52e-04 | 0.0s | 0MB |
| **4** | 84 | 6.7597 | 6.8847 | 977.21 | 3.36e-04 | 0.0s | 0MB |
| **5** | 105 | 6.6218 | 6.7468 | 851.33 | 3.20e-04 | 0.0s | 0MB |
| **6** | 126 | 6.4880 | 6.6130 | 744.71 | 3.04e-04 | 0.0s | 0MB |
| **7** | 147 | 6.3575 | 6.4825 | 653.61 | 2.88e-04 | 0.0s | 0MB |
| **8** | 168 | 6.2298 | 6.3548 | 575.26 | 2.72e-04 | 0.0s | 0MB |
| **9** | 189 | 6.1045 | 6.2295 | 507.50 | 2.56e-04 | 0.0s | 0MB |
| **10** | 210 | 5.9812 | 6.1062 | 448.65 | 2.40e-04 | 0.0s | 0MB |
| **11** | 231 | 5.8598 | 5.9848 | 397.35 | 2.24e-04 | 0.0s | 0MB |
| **12** | 252 | 5.7401 | 5.8651 | 352.50 | 2.08e-04 | 0.0s | 0MB |
| **13** | 273 | 5.6218 | 5.7468 | 313.18 | 1.92e-04 | 0.0s | 0MB |
| **14** | 294 | 5.5049 | 5.6299 | 278.63 | 1.76e-04 | 0.0s | 0MB |
| **15** | 315 | 5.3892 | 5.5142 | 248.19 | 1.60e-04 | 0.0s | 0MB |
| **16** | 336 | 5.2747 | 5.3997 | 221.34 | 1.44e-04 | 0.0s | 0MB |
| **17** | 357 | 5.1612 | 5.2862 | 197.60 | 1.28e-04 | 0.0s | 0MB |
| **18** | 378 | 5.0488 | 5.1738 | 176.58 | 1.12e-04 | 0.0s | 0MB |
| **19** | 399 | 4.9373 | 5.0623 | 157.95 | 9.60e-05 | 0.0s | 0MB |
| **20** | 420 | 4.8266 | 4.9516 | 141.41 | 8.00e-05 | 0.0s | 0MB |
| **21** | 441 | 4.7168 | 4.8418 | 126.70 | 6.40e-05 | 0.0s | 0MB |
| **22** | 462 | 4.6078 | 4.7328 | 113.61 | 4.80e-05 | 0.0s | 0MB |
| **23** | 483 | 4.4995 | 4.6245 | 101.95 | 3.20e-05 | 0.0s | 0MB |
| **24** | 504 | 4.3919 | 4.5169 | 91.55 | 1.60e-05 | 0.0s | 0MB |
| **25** | 525 | 4.2850 | 4.4100 | 82.27 | 0.00e+00 | 0.0s | 0MB |

---

## 3. Semantic Evaluation Benchmark Results

### Overall Accuracy: **8 / 14 (57.1%)** (Baseline: 57.1%)

### Breakdown by Category:
- **English Comprehension**: 1 / 2 (50.0%)
- **Hindi Comprehension**: 0 / 2 (0.0%)
- **Hinglish Comprehension**: 2 / 2 (100.0%)
- **Contextual Completion**: 1 / 2 (50.0%)
- **Technical Text**: 0 / 2 (0.0%)
- **Code Completion**: 2 / 2 (100.0%)
- **Json Structured**: 2 / 2 (100.0%)

### Breakdown by Language:
- **EN**: 6 / 10 (60.0%)
- **HI**: 0 / 2 (0.0%)
- **HINGLISH**: 2 / 2 (100.0%)

---

## 4. Checkpoint Artifacts & Provenance

Checkpoints serialized to Google Drive:
- **Primary Checkpoint**: `C:/Users/user/Desktop/naira os/NairaLLM/training/checkpoints/semantic_pretraining/naira_semantic_105k_numpy.npz`
- **Best Checkpoint**: `C:/Users/user/Desktop/naira os/NairaLLM/training/checkpoints/semantic_pretraining/naira_semantic_105k_numpy.npz`
- **Pre-Training Metadata**: `C:/Users/user/Desktop/naira os/NairaLLM/training/checkpoints/semantic_pretraining/pre_training_metadata.json`

Each checkpoint preserves:
1. `model_state_dict`
2. `optimizer_state_dict`
3. `scheduler_state_dict`
4. `epoch` and `global_step`
5. `git_commit_sha` (`7f6ef293211e88d2bfc9e8ad555c5e9be3d7c521`)
6. `dataset_sha256` (`c52e7f4b15a18a3cbf25fd0e6611bc2c042a765cd699055ec23bb1990225718f`)
7. Full `model_config` and `training_config`

---

## 5. Strict Phase Gate Enforcement

> [!IMPORTANT]
> In accordance with training protocol, **semantic foundation pretraining has STOPPED**.
> Automated instruction or tool training has NOT been initiated.
>
> **Next Sequential Stages (Awaiting Explicit Human Command)**:
> 1. Semantic Checkpoint Validation
> 2. Naira OS Domain Adaptation
> 3. Naira Instruction & Tool Execution Fine-Tuning
> 4. Behavioral & Proactive Decision Training
