# NairaLLM V1.5 — Locked Dataset A Final Verification Report

**Lock Timestamp**: 2026-08-17 15:39:45  
**Locked Dataset**: `semantic_pretrain_v1_5_final.jsonl`  
**Dataset SHA-256**: `015b4655bde092005b31195025e96df6e80702e7975f05ebf0c6072c1b29ff8f`  
**File Size**: 329,013 bytes  
**Git Commit SHA**: `b9c64ea9e193008426aa56075492c91135944d61` (`main`)  
**Status**: **LOCKED & VERIFIED FOR CLOUD T4 GPU PRETRAINING**  

---

## 1. Root Cause Analysis: Hash Discrepancy Resolution

| Environment / Stream | Line Ending | File Size | SHA-256 Hash | Content Parity |
| :--- | :---: | :---: | :--- | :---: |
| **Windows Workstation (Raw Checkout)** | `CRLF` (`\r\n`) | 329,350 bytes | `c52e7f4b15a18a3cbf25fd0e6611bc2c042a765cd699055ec23bb1990225718f` | Identical (337 records) |
| **Google Colab / Linux (Standard Clone)** | `LF` (`\n`) | 329,013 bytes | `015b4655bde092005b31195025e96df6e80702e7975f05ebf0c6072c1b29ff8f` | Identical (337 records) |
| **Locked Canonical File (`final.jsonl`)** | `LF` (`\n`) | **329,013 bytes** | **`015b4655bde092005b31195025e96df6e80702e7975f05ebf0c6072c1b29ff8f`** | **Canonical Target** |

### Key Diagnostic Findings:
1. **Zero Content Drift**: Character count (182,750), record count (337), and BPE token count (105,141 raw / 105,478 packed) are **100% identical** across both versions.
2. **Byte Difference**: Exactly 337 bytes ($329,350 - 329,013 = 337$), corresponding to the single byte carriage return (`\r`) on each of the 337 lines when checked out on Windows with `core.autocrlf = true`.
3. **Cross-Platform Invariance**: `.gitattributes` has been added with `*.jsonl text eol=lf` to enforce deterministic LF line endings and immutable SHA-256 hashes across all operating systems.

---

## 2. Locked Dataset Specifications

| Metric | Verified Value |
| :--- | :--- |
| **Canonical File** | `NairaLLM/dataset/semantic_corpus/semantic_pretrain_v1_5_final.jsonl` |
| **Immutable SHA-256** | **`015b4655bde092005b31195025e96df6e80702e7975f05ebf0c6072c1b29ff8f`** |
| **Total Records** | **337 records** |
| **Total Characters** | **182,750 characters** |
| **Raw BPE Tokens** | **105,141 tokens** |
| **Packed Tokens (with EOS)** | **105,478 tokens** |
| **Tokenizer Vocab Size** | **1,509 tokens** (`NairaLLM/model/tokenizer/naira_tokenizer.json`) |
| **Tokenizer SHA-256** | `71f6f8d70b56b1ceb4de95013fd70193e7080485ddc5abfe875193f3b83b42ad` |

---

## 3. Dataset Distribution & Provenance

### Language Breakdown:
- **English (`en`)**: 236 records (70.0%)
- **Hindi (`hi`)**: 52 records (15.4%)
- **Hinglish (`hinglish`)**: 49 records (14.5%)

### Domain Coverage (22 Domains):
- **Natural Language**: 38 records
- **Hindi Linguistics**: 48 records
- **Hinglish Discourse**: 45 records
- **Operating Systems**: 24 records
- **Programming Python**: 4 records
- **Documentation Apis**: 2 records
- **Structured Data**: 12 records
- **Naira Architecture**: 7 records
- **Computer Architecture**: 13 records
- **Networking**: 14 records
- **Databases**: 17 records
- **Algorithms**: 15 records
- **Data Structures**: 10 records
- **Programming**: 29 records
- **Software Engineering**: 15 records
- **Apis Http**: 8 records
- **Security**: 14 records
- **Linux Cli**: 6 records
- **Documentation**: 5 records
- **Technical Explanations**: 5 records
- **Error Messages Diagnostics**: 5 records
- **Web Development**: 1 records

---

## 4. Training Runner & Config Integration

The following configuration and runner files have been updated to target the locked dataset:
1. `NairaLLM/configs/colab_t4_config.json` -> points to `semantic_pretrain_v1_5_final.jsonl`
2. `NairaLLM/training/scripts/run_105k_semantic_pretraining.py` -> verifies `015b4655bde092005b31195025e96df6e80702e7975f05ebf0c6072c1b29ff8f`
3. `NairaLLM/training/scripts/train_gpu.py` -> default path updated to `semantic_pretrain_v1_5_final.jsonl`
4. `NairaLLM/training/cloud/colab_setup.py` -> default path updated to `semantic_pretrain_v1_5_final.jsonl`
5. `NairaLLM/training/cloud/nairallm_v1_5_free_gpu_pilot.ipynb` -> points to locked dataset and SHA-256

---

> [!IMPORTANT]
> **Dataset Version**: **LOCKED & IMMUTABLE**.
> Training has **NOT** been started. The repository is ready for Colab execution.
