# FINAL ONE-SHOT CONTINUOUS TRAINING PLAN (MASTER PROMPT 7)
**Project**: Naira OS AI Assistant Model (NairaLLM)  
**Target Model**: NairaLLM-30M (29,368,832 tied parameters, context length 2048 tokens)  
**Execution Paradigm**: ONE-SHOT Single Continuous Invocation (`train_final_once.py`)  
**Hardware Requirement**: Google Colab Free Tesla T4 (16GB GDDR6, $0.00 compute policy)  
**Verdict**: `READY_FOR_MASTER_PROMPT_8 = true`

---

## 1. Source of Truth & Architecture

| Layer | Authority / Storage Location | Purpose |
| :--- | :--- | :--- |
| **Code & Configs** | **GitHub Repository** | Python source, tokenizer configs, tool catalog schemas |
| **Training Datasets**| **GitHub Repository** (`NairaLLM/dataset/final/`) | Canonical Datasets A, B, and C with registered SHA-256 |
| **Evaluation Suite** | **GitHub Repository** (`final_v1_benchmark_v3.py`) | 800 unseen test prompts with strict AST rubrics |
| **Model Checkpoints**| **Google Drive** (`/content/drive/MyDrive/Naira-Training/checkpoints/final/`) | Weights `.pt`, optimizer states, run manifests |
| **Compute Engine** | **Google Colab Free GPU** | Ephemeral Tesla T4 16GB execution container |

---

## 2. 5-Phase Continuous Curriculum with Anti-Forgetting Replay

The training job runs as **one continuous Python process** with an internal multi-phase curriculum:

```
[Phase A: Semantic Foundation] (2 epochs, lr=5e-4)
       │
       ▼
[Phase B: Naira Domain & Identity] (2 epochs, lr=4e-4 + 15% Phase A Replay)
       │
       ▼
[Phase C: Cognition & DAG Planning] (2 epochs, lr=3e-4 + 15% Phase A/B Replay)
       │
       ▼
[Phase D: 102 Tool Contracts & Verification] (3 epochs, lr=2e-4 + 20% Replay Mixing)
       │
       ▼
[Phase E: Jarvis Autonomy L0-5 & Safety] (3 epochs, lr=1e-4 + 25% Full Replay)
       │
       ▼
[FINAL_NAIRALLM_30M.PT] (Zero-Heuristic Benchmark V3 Validation Gate)
```

---

## 3. Optimizer & Hyperparameter Plan (30M Model)

| Parameter | Configuration Value | Mathematical Rationale |
| :--- | :--- | :--- |
| **Architecture** | **NairaLLM-30M** | `d_model=512, layers=8, heads=8, d_ff=1536, ctx=2048, vocab=4096` |
| **Tied Parameter Count** | **29,368,832** | Analytically verified exact match |
| **Optimizer** | **AdamW** | $\beta_1=0.9, \beta_2=0.95, \epsilon=10^{-8}, \text{weight\_decay}=0.1$ |
| **Learning Rate Schedule** | **Cosine Decay** | Peak $5.0 	imes 10^-4 	o$ Min $5.0 	imes 10^-5$ (5% linear warmup) |
| **Batching Strategy** | **Micro-batch 4, Grad Accum 8** | **Effective Batch Size = 32 sequences (65,536 tokens/step)** |
| **Precision** | **FP16 AMP** (`torch.cuda.amp`) | Memory optimization with `GradScaler` |
| **Gradient Clipping** | **Max Norm 1.0** | Prevents attention score divergence during early phases |

---

## 4. Checkpoint Persistence & Verification Protocol

Every recovery checkpoint and the final model weight file are verified using a 5-step strict protocol:
1. **Local Disk Write**: Save `.pt` bundle with model state, optimizer state, scheduler, and config SHA.
2. **Reload Validation**: Load state dict locally to verify uncorrupted tensor integrity.
3. **Google Drive Sync**: Copy `.pt` and `.json` metadata to `/content/drive/MyDrive/Naira-Training/checkpoints/final/`.
4. **Checksum Match**: Calculate and assert identical SHA-256 hashes between local disk and Google Drive.
5. **Run Manifest Update**: Append phase milestone and validation loss to `run_manifest.json`.

---

## 5. Runtime & VRAM Budget on Tesla T4 (16GB)

| Resource Metric | Estimated Value | Headroom / Margin |
| :--- | :--- | :--- |
| **Model Weights (FP16)** | **58.7 MB** | Minimal footprint |
| **Peak VRAM During Training** | **3.2 GB** | **12.8 GB free VRAM (20.0% utilization)** |
| **Training Token Volume** | **~1,450,000 tokens** | Multi-phase curriculum allocation |
| **Estimated Training Time** | **~22.5 minutes** | Fully fits inside single free Colab session |
| **Total Financial Cost** | **$0.00** | Strict Free Cloud Policy adhered |

---

## 6. STOP Gate Verdict

```
============================================================
FINAL TRAINING PLAN VERDICT: READY_FOR_MASTER_PROMPT_8 = true
- Zero model training executed.
- Single continuous training script (train_final_once.py) tested & verified.
- One-click Colab notebook (nairallm_final_once.ipynb) configured.
- Ready to proceed to Master Prompt 8 (Final Pre-Training Lock Audit).
============================================================
```
