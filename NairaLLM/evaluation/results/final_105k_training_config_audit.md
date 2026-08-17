# NairaLLM V1.5 — Final Training Configuration Audit Before 105K Pilot

**Audit Date**: 2026-08-17  
**Audit Target**: Cloud Pretraining Pipeline & Architecture for 105K-Token Dataset A Pilot  
**Audit Status**: **PASSED & FULLY VERIFIED**  
**Training State**: **STOPPED (Awaiting Launch Authorization)**  

---

## 1. Executive Summary & Core Findings

Following the successful completion of the 10-point cloud smoke test on Google Colab (Tesla T4, 14.56 GB VRAM, CUDA/PyTorch/AMP verified), this formal audit investigated the apparent parameter discrepancy between the **178,816-parameter smoke test model** and the **~1.43M-parameter earlier semantic training model**.

### Key Verdict
1. **The discrepancy is 100% INTENTIONAL and mathematically verified.**
2. **The 178,816-parameter model is strictly a smoke-test probe** defined in `NairaLLM/training/cloud/run_smoke_test.py` (`d_model=64, num_layers=2, d_ff=128`) designed to execute all 10 sanity checks in <1 second without burning compute.
3. **The production semantic pretraining model** defined in `NairaLLM/configs/colab_t4_config.json`, `NairaLLM/training/scripts/train_gpu.py`, and `NairaLLM/training/scripts/run_semantic_pilot.py` is a 4-layer Transformer (`d_model=128, num_layers=4, d_ff=512`).
   - In **PyTorch** with tied token embeddings (`tie_embeddings=True`), it has exactly **1,242,880 parameters**.
   - In **Pure-NumPy** (or PyTorch with untied output projection), it has exactly **1,436,032 parameters** ($1,242,880 + 193,152 = 1,436,032$).
4. **No misconfiguration exists in the architecture or training pipelines.**
5. Full training has **NOT** been started. Execution is paused awaiting user confirmation.

---

## 2. Parameter Discrepancy Resolution: Exact Mathematical Breakdown

| Model Architecture | Backend | Token Embeddings | Per-Layer Parameters ($L$) | $N$ Layers Subtotal | RMSNorm Final | Output Projection | Total Trainable Parameters |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Cloud Smoke Probe** (`d_model=64, L=2, d_ff=128`) | PyTorch (CUDA/CPU) | $1,509 \times 64 = 96,576$ | $41,088$ | $2 \times 41,088 = 82,176$ | $64$ | Tied ($0$) | **178,816** |
| **Cloud Smoke Probe** (`d_model=64, L=2, d_ff=128`) | Pure-NumPy Fallback | $96,576$ | $41,088$ | $82,176$ | $64$ | Untied ($96,576$) | **275,392** |
| **Production Pretrainer** (`d_model=128, L=4, d_ff=512`) | **PyTorch (Tied)** | $1,509 \times 128 = 193,152$ | $262,400$ | $4 \times 262,400 = 1,049,600$ | $128$ | **Tied ($0$)** | **1,242,880** |
| **Production Pretrainer** (`d_model=128, L=4, d_ff=512`) | Pure-NumPy / Untied | $193,152$ | $262,400$ | $1,049,600$ | $128$ | Untied ($193,152$) | **1,436,032** |

### Mathematical Formulas

#### Per Layer ($d_{\text{model}}, d_{\text{ff}}$):
$$\text{Params}_{\text{layer}} = \underbrace{d_{\text{model}}}_{\text{RMSNorm}} + \underbrace{4 \times (d_{\text{model}} \times d_{\text{model}})}_{\text{CausalSelfAttention (Q, K, V, Out)}} + \underbrace{d_{\text{model}}}_{\text{RMSNorm}} + \underbrace{3 \times (d_{\text{model}} \times d_{\text{ff}})}_{\text{SwiGLU (w1, w2, w3)}}$$

- For Smoke Probe ($d_{\text{model}}=64, d_{\text{ff}}=128$):
  $$\text{Params}_{\text{layer}} = 64 + 4(4096) + 64 + 3(8192) = 64 + 16384 + 64 + 24576 = 41,088$$
- For Production Model ($d_{\text{model}}=128, d_{\text{ff}}=512$):
  $$\text{Params}_{\text{layer}} = 128 + 4(16384) + 128 + 3(65536) = 128 + 65536 + 128 + 196608 = 262,400$$

#### Full Model (PyTorch with Tied Embeddings):
$$\text{Params}_{\text{total}} = (\text{vocab\_size} \times d_{\text{model}}) + (N \times \text{Params}_{\text{layer}}) + d_{\text{model}}$$

- For Smoke Probe ($N=2$):
  $$\text{Params} = 96,576 + (2 \times 41,088) + 64 = 96,576 + 82,176 + 64 = \mathbf{178,816}$$
- For Production Model ($N=4$):
  $$\text{Params} = 193,152 + (4 \times 262,400) + 128 = 193,152 + 1,049,600 + 128 = \mathbf{1,242,880}$$
- When untied (NumPy backend):
  $$\text{Params}_{\text{untied}} = 1,242,880 + 193,152 = \mathbf{1,436,032}$$

---

## 3. Comprehensive 16-Point Inspection Checklist

| # | Inspection Item | Verification Result | Exact Verified Value / Status |
| :---: | :--- | :---: | :--- |
| **1** | Production Model Architecture | `PASSED` | `NairaTransformer` (Causal Decoder-Only Transformer) |
| **2** | Model Class in `train_gpu.py` | `PASSED` | `NairaTransformer` from `NairaLLM.model.architecture.naira_transformer` |
| **3a** | Hidden Dimension (`d_model`) | `PASSED` | **`128`** |
| **3b** | Number of Layers (`num_layers`) | `PASSED` | **`4`** |
| **3c** | Attention Heads (`num_heads` / `num_kv_heads`) | `PASSED` | **`4` / `4`** (`d_head = 32`) |
| **3d** | Intermediate Dimension (`d_ff`) | `PASSED` | **`512`** (SwiGLU gated activation) |
| **3e** | Vocabulary Size (`vocab_size`) | `PASSED` | **`1,509`** (BPE token vocabulary) |
| **3f** | Context Length (`max_seq_len`) | `PASSED` | **`256`** (Pilot) / configurable up to **`512`** for full run |
| **3g** | Total Parameter Count | `PASSED` | **`1,242,880`** (PyTorch Tied) / **`1,436,032`** (Untied) |
| **4** | Exact Dataset Path | `PASSED` | `NairaLLM/dataset/semantic_corpus/semantic_pretrain_v1_5_expanded.jsonl` |
| **5** | Dataset Version & SHA-256 Hash | `PASSED` | `c52e7f4b15a18a3cbf25fd0e6611bc2c042a765cd699055ec23bb1990225718f` (337 records, 105,141 tokens, 329,350 bytes) |
| **6** | Exact Tokenizer Path & Hash | `PASSED` | `NairaLLM/model/tokenizer/naira_tokenizer.json` (`71f6f8d70b56b1ceb4de95013fd70193e7080485ddc5abfe875193f3b83b42ad`) |
| **7** | Micro-Batch Size | `PASSED` | **`4`** (per-step device batch) |
| **8** | Gradient Accumulation Steps | `PASSED` | **`4`** (Effective batch size = **`16`**) |
| **9** | Learning Rate & Schedule | `PASSED` | Peak LR = **`4e-4`** (`0.0004`), Min LR = **`1e-5`** (`0.00001`), Weight Decay = **`0.01`** |
| **10** | Optimizer | `PASSED` | **`AdamW`** ($\beta_1 = 0.9, \beta_2 = 0.95, \epsilon = 10^{-8}$, weight decay = 0.01) |
| **11** | LR Scheduler | `PASSED` | **`CosineAnnealingLR`** with warmup |
| **12** | AMP Precision | `PASSED` | **`FP16` Automatic Mixed Precision** (`torch.cuda.amp.autocast` + `GradScaler`) |
| **13** | Validation Split | `PASSED` | **90% Train / 10% Validation** (Packed token block evaluation) |
| **14** | Checkpoint Directory | `PASSED` | Persistent: `/content/drive/MyDrive/Naira-Training/checkpoints/semantic_pretrain_pilot` |
| **15** | Checkpoint & Resume Behavior | `PASSED` | Full parity verified ($\Delta < 10^{-5}$); preserves model, optimizer, scheduler, epoch, step, git SHA, dataset SHA |
| **16** | Smoke vs Production Distinction | `PASSED` | **Intentionally different**: 178K probe for <1s sanity check vs 1.24M/1.43M for semantic learning |

---

## 4. Clear Answers to Mandatory Audit Questions

### A. What exact model will train on the 105K-token Dataset A?
The model is **`NairaTransformer`**, instantiated using the `NairaModelConfig` specification. It is a modern causal decoder-only transformer featuring:
- **RMSNorm** pre-normalization (`eps = 1e-5`)
- **Rotary Position Embeddings (RoPE)** (`rope_theta = 10,000.0`)
- **SwiGLU** gated feed-forward activation layers
- **Multi-Head Causal Self-Attention** with Key-Value caching
- **Weight Tying** between token embeddings and the LM output projection matrix

### B. How many parameters?
- In **PyTorch GPU/CPU training** (production target with `tie_embeddings=True`): **`1,242,880` parameters** (~1.24M).
- In **Pure-NumPy CPU verification** (untied embeddings): **`1,436,032` parameters** (~1.44M).
- The difference of $193,152$ parameters is purely the shared vs. duplicated embedding/output weight matrix ($1,509 \times 128 = 193,152$).

### C. What exact training config?
- **Device**: Google Colab Tesla T4 GPU (14.56 GB VRAM)
- **Precision**: FP16 Automatic Mixed Precision (`torch.cuda.amp.autocast` + `GradScaler`)
- **Micro-Batch Size**: 4
- **Gradient Accumulation Steps**: 4
- **Effective Batch Size**: 16 sequences
- **Sequence Length (`max_seq_len`)**: 256 tokens
- **Optimizer**: AdamW ($\text{lr} = 4 \times 10^{-4}, \beta = (0.9, 0.95), \text{weight\_decay} = 0.01$)
- **Scheduler**: Cosine Annealing with Warmup ($\eta_{\text{min}} = 1 \times 10^{-5}$)
- **Gradient Norm Clipping**: 1.0
- **Validation Split**: 90% Train / 10% Validation

### D. What exact dataset?
- **Dataset**: `semantic_pretrain_v1_5_expanded.jsonl` (Dataset A)
- **Path**: `NairaLLM/dataset/semantic_corpus/semantic_pretrain_v1_5_expanded.jsonl`
- **SHA-256 Hash**: `c52e7f4b15a18a3cbf25fd0e6611bc2c042a765cd699055ec23bb1990225718f`
- **File Size**: 329,350 bytes
- **Total Records**: 337 multi-domain records
- **Total BPE Tokens**: 105,141 raw tokens (105,478 with EOS packing)
- **Provenance**: Zero synthetic leakage, 0 duplicates, 20 balanced semantic domains (English, Hindi, Hinglish, reasoning, code, JSON, tools).

### E. Is the 178,816-parameter smoke model ONLY a smoke-test model?
**YES.** The 178,816-parameter model (`d_model=64, num_layers=2, d_ff=128`) in `run_smoke_test.py` is solely a fast sanity probe designed to verify that the hardware, CUDA, AMP, autograd, optimizer, disk I/O, checkpoint save/reload, and resumption mechanisms work without allocating meaningful memory or compute.

### F. Is the ~1.43M model the intended semantic-pretraining model?
**YES.** The 4-layer architecture (`d_model=128, num_layers=4, num_heads=4, d_ff=512`) is the intended semantic-pretraining model. It has:
- **1,242,880 parameters** when running in PyTorch with parameter tying enabled.
- **1,436,032 parameters** when running in NumPy or with separate output weights.
The earlier reported "1,436,032" was from the NumPy execution where embedding and output weights were stored as two separate NumPy arrays.

### G. Is anything incorrectly configured?
**NO.** All configuration files, training scripts, tokenizer definitions, dataset hashes, and cloud notebooks are in complete alignment.

---

## 5. Cloud Sizing & Execution Envelope

| Metric | Google Colab Free T4 GPU Allocation | Estimated 105K Pilot Usage | Safety Margin |
| :--- | :--- | :--- | :--- |
| **VRAM** | 14.56 GB | ~450 MB – 1.2 GB | **>13.3 GB Headroom (>91% free)** |
| **Compute Units Cost** | Free Tier ($0.00) | 0 Paid Compute Units | **Strict $0.00 Policy Maintained** |
| **Estimated Duration (10-25 Epochs)** | Continuous Free Session (~12h limit) | **6 – 15 minutes** | **Safe from timeout** |
| **Persistent Storage** | Mounted Google Drive | Checkpoint bundle ~12 MB | **100% Persistent** |

---

## 6. Audit Conclusion & Stop Gate

> [!IMPORTANT]
> **Audit Status**: **PASSED**  
> All 16 configuration and architecture items have been thoroughly audited, mathematically reconciled, and verified.
>
> In accordance with instructions, **training has NOT been started**.
> The system has **STOPPED** and is ready to launch the 105K semantic pretraining pilot upon your command.
