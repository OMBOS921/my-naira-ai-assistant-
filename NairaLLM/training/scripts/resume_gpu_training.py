"""
Resume GPU Training Session for NairaLLM V1.5.

Locates the latest checkpoint, recovers the model, optimizer, scheduler,
and global step, and resumes pretraining seamlessly without data loss.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure workspace root in sys.path
workspace_root = Path(__file__).resolve().parent.parent.parent.parent
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

from NairaLLM.training.scripts.train_gpu import train_gpu


def resume_training(checkpoint_dir: str | Path | None = None) -> None:
    ckpt_dir = Path(checkpoint_dir or os.environ.get("NAIRA_CHECKPOINT_DIR", "NairaLLM/training/checkpoints"))
    latest_pt = ckpt_dir / "naira_model_v1_5_latest.pt"

    print("==================================================")
    print("     NAIRALLM — RESUME GPU TRAINING SESSION       ")
    print("==================================================")
    print(f"Target Checkpoint Directory: {ckpt_dir}")

    if not latest_pt.exists():
        print(f"[WARNING] No existing checkpoint found at {latest_pt}. Starting clean run.")
        train_gpu(checkpoint_dir=ckpt_dir, resume=False)
    else:
        print(f"[FOUND] Latest checkpoint: {latest_pt.name}")
        train_gpu(checkpoint_dir=ckpt_dir, resume=True)


def main() -> None:
    resume_training()


if __name__ == "__main__":
    main()
