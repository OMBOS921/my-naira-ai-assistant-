# Free Cloud GPU Training Guide for NairaLLM (GitHub + Colab Workflow)

This guide details how to execute **NairaLLM Semantic Pretraining & Pilot Evaluation** on Google Colab's Free Tesla T4 GPU using GitHub as the single canonical source of truth.

---

## 1. Architecture & Source-of-Truth

```text
Local Naira OS Repository
          ↓
   Antigravity Edits
          ↓
      Git Commit
          ↓
     GitHub Push (Canonical Source of Truth)
          ↓
Google Colab clones / pulls from GitHub
          ↓
Free T4 GPU Training (AMP + Mixed Precision)
          ↓
Persistent Checkpoints saved to Google Drive (/content/drive/MyDrive/Naira-Training/checkpoints/)
```

> [!NOTE]
> **Zero Cost Policy**: `USE_PAID_COMPUTE = False`. No Colab Pro or paid compute units are required.
> Checkpoints are serialized to Google Drive, ensuring that weights persist across runtime restarts while keeping Git clean of large binary weights.

---

## 2. Google Colab Training Notebook

The primary automated training notebook is:
[`NairaLLM/training/cloud/nairallm_colab_setup.ipynb`](file:///c:/Users/user/Desktop/naira%20os/NairaLLM/training/cloud/nairallm_colab_setup.ipynb)

### How to Run in Google Colab:
1. Open [Google Colab](https://colab.research.google.com).
2. Go to **File** $\to$ **Upload notebook** $\to$ select `NairaLLM/training/cloud/nairallm_colab_setup.ipynb` (or open directly from GitHub).
3. Set Runtime: **Runtime** $\to$ **Change runtime type** $\to$ **T4 GPU** $\to$ **Save**.
4. Run the notebook cells sequentially:
   - **Step 1 (Environment Check)**: Verifies CUDA T4 GPU and enforces free tier policy.
   - **Step 2 (Google Drive Mount)**: Creates `/content/drive/MyDrive/Naira-Training/checkpoints/`.
   - **Step 3 (Repository Sync)**: Clones or pulls from canonical repository (`https://github.com/OMBOS921/my-naira-ai-assistant-.git`). Supports private repositories via secure masked token prompt.
   - **Step 4 (Provenance Audit)**: Prints Git SHA, branch, Dataset A SHA-256, tokenizer vocab size, and model config.
   - **Step 5 (Smoke Test)**: Runs the 10-step GPU smoke test.
   - **Step 6 (Pilot Training)**: Runs the short 10-epoch pilot with semantic evaluation and STOP gate.
   - **Step 7 (Full Training)**: Requires explicit `RUN_FULL_TRAINING = True` to launch full run.

---

## 3. Checkpoint Artifacts & Provenance

Every checkpoint saved to Google Drive includes:
- `model_state_dict` (Transformer weights)
- `optimizer_state_dict` (AdamW optimizer momentum buffers)
- `scheduler_state_dict` (Cosine annealing LR schedule)
- `epoch` & `global_step`
- `git_commit_sha` & `git_branch`
- `dataset_version` & `dataset_sha256`
- `tokenizer_vocab_size`
- `training_config` & `model_config`
- `metrics` (`train_loss`, `val_loss`, `val_perplexity`)

Training is fully resumable at any time.
