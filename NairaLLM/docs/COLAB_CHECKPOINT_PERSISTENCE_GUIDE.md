# Google Colab NairaLLM Checkpoint Persistence Guide

This guide documents the persistent cloud checkpointing architecture for NairaLLM V1 training on free Google Colab (Tesla T4 GPU).

---

## 1. The Persistence Problem & Architecture

Google Colab instances run in ephemeral virtual machines. When a session disconnects, times out, or resets:
- The local filesystem (`/content/naira os/...`) is destroyed.
- GitHub only tracks code, configs, datasets, and metadata JSON files (binary `.pt` weights are omitted).

### The Solution: Automated Google Drive Backup & Auto-Restore
Every stage in `train_final_v1.py` automatically synchronizes with Google Drive:

```
Google Drive Persistent Root:
/content/drive/MyDrive/Naira-Training/checkpoints/final_v1/
├── semantic/
│   ├── nairallm_v1_semantic_checkpoint.pt
│   ├── nairallm_v1_semantic_checkpoint_metadata.json
│   └── nairallm_v1_semantic_manifest.json
├── domain/
│   ├── nairallm_v1_domain_checkpoint.pt
│   ├── nairallm_v1_domain_checkpoint_metadata.json
│   └── nairallm_v1_domain_manifest.json
├── cognition/
│   ├── nairallm_v1_cognition_checkpoint.pt
│   ├── nairallm_v1_cognition_checkpoint_metadata.json
│   └── nairallm_v1_cognition_manifest.json
├── tools/
├── behavior/
└── final/
```

---

## 2. Standard Google Colab Setup (Every Session)

At the top of your Google Colab notebook, always mount Google Drive first:

```python
# Cell 1: Mount Google Drive
from google.colab import drive
drive.mount('/content/drive')

# Cell 2: Clone or Pull Latest Code
%cd /content
!git clone https://github.com/OMBOS921/my-naira-ai-assistant-.git "naira os" || (cd "naira os" && git fetch origin main && git reset --hard origin/main)
%cd "/content/naira os"

# Cell 3: Verify Pre-Flight Checks
!python NairaLLM/training/scripts/stage_0_preflight.py
```

---

## 3. How Checkpoint Auto-Discovery & Auto-Restore Works

When launching any stage:
```bash
!python NairaLLM/training/scripts/train_final_v1.py --stage <target_stage>
```

1. **Predecessor Discovery**:
   - The trainer queries `CheckpointChainManager.find_latest_checkpoint(predecessor_stage)`.
   - If the `.pt` weights are present locally, it uses them immediately.
   - If `.pt` weights are missing locally (e.g. fresh Colab session), it **automatically copies the verified `.pt` weights and metadata from Google Drive** into `/content/naira os/NairaLLM/training/checkpoints/<predecessor>/`.
2. **Lineage Invariant**:
   - If predecessor weights cannot be found locally or on Google Drive, training **aborts immediately** (`FileNotFoundError`).
   - It will **never** train a fresh model from scratch for downstream stages.
3. **Automatic Persistent Backup**:
   - Upon completing the epoch loop, the trainer saves `.pt` weights locally.
   - Verifies byte size and integrity.
   - Immediately copies `.pt` weights, metadata, and manifest to `/content/drive/MyDrive/Naira-Training/checkpoints/final_v1/<target_stage>/`.

---

## 4. Stage-by-Stage Colab Commands

### Stage 1 (Semantic Pretraining)
```bash
!python NairaLLM/training/scripts/train_final_v1.py \
    --stage semantic \
    --config NairaLLM/configs/final_nairallm_v1.json
```

### Stage 2 (Domain Grounding)
```bash
!python NairaLLM/training/scripts/train_final_v1.py \
    --stage domain \
    --config NairaLLM/configs/final_nairallm_v1.json
```

### Stage 3 (Cognition & Planning)
```bash
!python NairaLLM/training/scripts/train_final_v1.py \
    --stage cognition \
    --config NairaLLM/configs/final_nairallm_v1.json
```

### Stage 4 (Tool Calling & Contracts)
```bash
!python NairaLLM/training/scripts/train_final_v1.py \
    --stage tools \
    --config NairaLLM/configs/final_nairallm_v1.json
```

### Stage 5 (Jarvis Behavior & Safety)
```bash
!python NairaLLM/training/scripts/train_final_v1.py \
    --stage behavior \
    --config NairaLLM/configs/final_nairallm_v1.json
```
