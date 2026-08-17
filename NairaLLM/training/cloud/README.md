# Free Cloud GPU Training Guide for NairaLLM V1.5

This guide details how to execute **NairaLLM V1.5 Semantic Pretraining** on free cloud GPU tiers (Google Colab and Kaggle Notebooks) while maintaining your local machine as the primary development and control workstation.

---

## 1. Quick Environment Diagnostics

Before initiating any training run, run the diagnostic checker:

```bash
python NairaLLM/training/cloud/check_environment.py
```

This will automatically inspect:
- Python & PyTorch versions
- CUDA availability, GPU device name, compute capability, and VRAM
- Recommended batch size, gradient accumulation steps, and precision mode.

---

## 2. Google Colab Workflow (Primary Target)

### Step 1: Open Google Colab with GPU
1. Go to [Google Colab](https://colab.research.google.com).
2. Click **Runtime** $\to$ **Change runtime type** $\to$ Select **T4 GPU** (or **L4 GPU** if available).

### Step 2: Clone Repository & Setup
In a Colab cell, run:
```bash
!git clone https://github.com/YOUR_REPO/naira-os.git
%cd naira-os
!pip install -r requirements.txt
!pip install torch torchvision
```

### Step 3: Mount Google Drive & Run Pretraining
```python
from NairaLLM.training.cloud.colab_setup import setup_colab_environment
paths = setup_colab_environment(mount_drive=True)

# Run GPU Training with automatic mixed precision and Drive checkpointing
!python -m NairaLLM.training.scripts.train_gpu --epochs 30 --batch-size 8 --grad-accum 4
```

### Step 4: Resuming an Interrupted Session
If Colab disconnects, simply reconnect the GPU runtime and run:
```bash
!python -m NairaLLM.training.scripts.resume_gpu_training
```
The trainer automatically locates the latest `.pt` checkpoint in Google Drive and resumes seamlessly from that exact step.

---

## 3. Kaggle Notebooks Workflow (Secondary Target)

### Step 1: Create Notebook with GPU
1. Go to [Kaggle Notebooks](https://www.kaggle.com/code).
2. Click **Settings** (right sidebar) $\to$ **Accelerator** $\to$ Select **GPU P100** or **GPU T4 x2**.

### Step 2: Clone & Configure
```bash
!git clone https://github.com/YOUR_REPO/naira-os.git /kaggle/working/naira-os
%cd /kaggle/working/naira-os
!pip install -r requirements.txt
```

### Step 3: Run Training
```bash
!python NairaLLM/training/cloud/kaggle_setup.py --run-training
```

### Step 4: Download Checkpoints
At the end of training, the script packages checkpoints to `/kaggle/working/nairallm_v1_5_checkpoints.zip` which you can download directly from the Kaggle file explorer to your local `NairaLLM/training/checkpoints/` directory.

---

## 4. Checkpoint Artifacts & Local Sync

Every training run saves:
- `naira_model_v1_5_latest.pt` (Complete PyTorch weights, optimizer state, step counter)
- `naira_model_v1_5_best.pt` (Lowest validation loss model)
- `naira_model_v1_5_metadata.json` (Training curves, hyperparameters, loss history)

To evaluate the trained model on your local laptop:
1. Download the `.pt` file and metadata to `NairaLLM/training/checkpoints/`.
2. Run the evaluation benchmark:
   ```bash
   python -m NairaLLM.evaluation.suites.semantic_pretraining_suite
   python -m NairaLLM.evaluation.suites.run_v1_4_generalization_evaluation
   ```

---

## 5. Free Cloud Resource Rules
- Strictly adhere to legitimate free-tier usage policies.
- Do not attempt to bypass provider timeouts or quotas.
- Use the built-in gradient accumulation and mixed precision settings to maximize efficiency within allowed session durations.
