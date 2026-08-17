# NairaLLM Final V1 — Checkpoint Recovery & Lineage Audit Report

- **Audit Timestamp**: `2026-08-17 15:53:15 UTC`
- **Git Commit SHA**: `81caaf5a889e5e6cf837e6a85fb56667f0fca920`
- **`DOMAIN_CHECKPOINT_LOST`**: **`True`**
- **Status**: **`READY_FOR_STAGE_2_RECOVERY_TRAINING`**

---

## 1. Search Findings & Root Cause

- **Target File**: `nairallm_v1_domain_checkpoint.pt`
- **Result**: **NOT FOUND IN PERSISTENT STORAGE** (`DOMAIN_CHECKPOINT_LOST = TRUE`)
- **Metadata Status**: Verified present (`nairallm_v1_domain_checkpoint_metadata.json`).

### Root Cause
Stage 2 domain training completed in an earlier Google Colab session before automated Google Drive persistence was enabled. When the Colab ephemeral virtual machine terminated, the binary .pt file was lost while git preserved code, configs, datasets, and metadata. The new FileNotFoundError safety check correctly blocked Stage 3 from starting from uninitialized scratch.

The safety check in `train_final_v1.py` correctly raised `FileNotFoundError` upon attempting to start Stage 3, preventing uninitialized weights training.

---

## 2. Recovery Foundation Verification

- **Predecessor Seed**: `NairaLLM/training/checkpoints/foundation/naira_semantic_105k_numpy.npz` (5.3 MB, verified & tracked).
- **Lineage Compatibility**: **`PASSED`** (Stage 2 domain accepts foundation seed).
- **Dataset B Domain Parity**: `c191394b76e884b84fd39f90f1d1fd7eb8e7b428c3be6233e8604fe952144a4a` (80 conversations, 5,713 tokens).
- **Persistence Protection**: New `InstructionDataCollator` and automated Google Drive backup are active.

---

## 3. Recovery Execution Steps

```python
# Cell 1: Mount Google Drive
from google.colab import drive
drive.mount('/content/drive')

# Cell 2: Sync Workspace to Latest Commit
%cd /content
!git clone https://github.com/OMBOS921/my-naira-ai-assistant-.git "naira os" || (cd "naira os" && git fetch origin main && git reset --hard origin/main)
%cd "/content/naira os"

# Cell 3: Pre-Flight Verification
!python NairaLLM/training/scripts/stage_0_preflight.py

# Cell 4: Run Recovery Stage 2 (Domain Training)
!python NairaLLM/training/scripts/train_final_v1.py \
    --stage domain \
    --config NairaLLM/configs/final_nairallm_v1.json

# Cell 5: Verify Google Drive Persistent Backup
!ls -lh /content/drive/MyDrive/Naira-Training/checkpoints/final_v1/domain/
```

---

## 4. Next Safe Step

Once Cell 4 completes, the `.pt` file will be permanently preserved in Google Drive at `/content/drive/MyDrive/Naira-Training/checkpoints/final_v1/domain/nairallm_v1_domain_checkpoint.pt`.
Stage 3 (`cognition`) can then be safely launched without weight loss risk.
