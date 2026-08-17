# NairaLLM Final V1 — Canonical Dataset Lock Audit

- **Audit Timestamp**: `2026-08-17 14:05:22 UTC`
- **Status**: **`ALL_DATASETS_LOCKED_AND_VERIFIED`**
- **Line Ending Policy**: `Strict LF (newline='\n', .gitattributes eol=lf)`

---

## 1. Verified Deterministic Hashes (LF Normalization)

| Dataset Pillar | Records | Tokens | Bytes | SHA-256 Hash | Line Ending | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Dataset A (Semantic Foundation)** | 337 | 105,141 | 329,013 | `015b4655bde092005b31195025e96df6e80702e7975f05ebf0c6072c1b29ff8f` | `LF (Pure)` | **MATCH / LOCKED** |
| **Dataset B (All Capabilities)** | 706 | 71,280 | 739,258 | `93fe24aef07873fa2fb5a76b5a17da775fe6296ba5b3b6e30823f8ab1c289095` | `LF (Pure)` | **MATCH / LOCKED** |
| **Dataset B (Domain Stage)** | 80 | 5,713 | 65,863 | `c191394b76e884b84fd39f90f1d1fd7eb8e7b428c3be6233e8604fe952144a4a` | `LF (Pure)` | **MATCH / LOCKED** |
| **Dataset B (Cognition Stage)** | 91 | 14,162 | 104,045 | `4a8e8de37c59be7a3d69704e3cbb0e2d388b021fbe056c6e1553fe4f0ff094c9` | `LF (Pure)` | **MATCH / LOCKED** |
| **Dataset B (Tools Stage)** | 535 | 51,405 | 569,350 | `583d88d0d2e2d1ca3c2e5f44635c7f7183d786d870dad646d1d577fc4d7bcdee` | `LF (Pure)` | **MATCH / LOCKED** |
| **Dataset C (Behavior & Autonomy)** | 68 | 8,911 | 54,280 | `aff52170796c80b1ae84ed7f1eb68393b8ef1c9b42869b2de8c8642910e66fc7` | `LF (Pure)` | **MATCH / LOCKED** |

---

## 2. Cross-Platform Parity Verification

- All dataset `.jsonl` files are generated with explicit `newline='\n'`.
- Repository `.gitattributes` enforces `*.jsonl text eol=lf` across Windows, macOS, and Linux (Google Colab).
- Bit-for-bit SHA-256 match between local pre-flight on Windows and cloud pre-flight on Linux.
