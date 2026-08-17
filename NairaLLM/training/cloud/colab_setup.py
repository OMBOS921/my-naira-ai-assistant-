"""
Google Colab Automated Setup & Pretraining Orchestration Script for NairaLLM V1.5.

Handles:
- Dynamic GPU detection (Tesla T4 / L4 / V100 / A100)
- Google Drive mounting for persistent checkpoint saving
- Environment variable configuration:
  - Checkpoints: /content/drive/MyDrive/Naira-Training/checkpoints/semantic_pretrain_pilot/
  - Dataset A: semantic_pretrain_v1_5_expanded.jsonl (337 records, 105,141 tokens)
- Zero-cost policy enforcement (no paid compute, no paid Colab compute units)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Ensure workspace root in sys.path
workspace_root = Path(__file__).resolve().parent.parent.parent.parent
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

from NairaLLM.training.cloud.check_environment import inspect_environment, print_diagnostic_report


def setup_colab_environment(dry_run: bool = False, mount_drive: bool = True) -> dict[str, str]:
    print("==================================================")
    print("     NAIRALLM — GOOGLE COLAB TRAINING SETUP       ")
    print("==================================================")

    env = inspect_environment()
    print_diagnostic_report(env)

    paths: dict[str, str] = {}
    is_colab = "google.colab" in sys.modules or os.path.exists("/content")

    if is_colab:
        print("[DETECTED] Running inside Google Colab environment.")
        if mount_drive and not dry_run:
            try:
                from google.colab import drive  # type: ignore
                drive_mount_point = "/content/drive"
                if not os.path.exists(drive_mount_point):
                    drive.mount(drive_mount_point)
                    print(f"[MOUNTED] Google Drive at {drive_mount_point}")

                colab_ckpt_dir = "/content/drive/MyDrive/Naira-Training/checkpoints/semantic_pretrain_pilot"
                os.makedirs(colab_ckpt_dir, exist_ok=True)
                paths["checkpoint_dir"] = colab_ckpt_dir
                print(f"[STORAGE] Persistent Google Drive checkpoint directory: {colab_ckpt_dir}")
            except Exception as exc:
                print(f"[WARNING] Could not mount Google Drive ({exc}). Using local /content/checkpoints")
                local_dir = "/content/Naira-Training/checkpoints/semantic_pretrain_pilot"
                os.makedirs(local_dir, exist_ok=True)
                paths["checkpoint_dir"] = local_dir
        else:
            local_dir = "/content/Naira-Training/checkpoints/semantic_pretrain_pilot"
            os.makedirs(local_dir, exist_ok=True)
            paths["checkpoint_dir"] = local_dir
    else:
        print("[LOCAL / WORKSTATION] Running outside Colab.")
        local_dir = str(workspace_root / "NairaLLM" / "training" / "checkpoints" / "semantic_pretrain_pilot")
        os.makedirs(local_dir, exist_ok=True)
        paths["checkpoint_dir"] = local_dir

    paths["dataset_path"] = str(
        workspace_root / "NairaLLM" / "dataset" / "semantic_corpus" / "semantic_pretrain_v1_5_expanded.jsonl"
    )
    paths["tokenizer_path"] = str(
        workspace_root / "NairaLLM" / "model" / "tokenizer" / "naira_tokenizer.json"
    )

    # Set environment variables
    os.environ["NAIRA_CHECKPOINT_DIR"] = paths["checkpoint_dir"]
    os.environ["NAIRA_DATASET_PATH"] = paths["dataset_path"]
    os.environ["NAIRA_TOKENIZER_PATH"] = paths["tokenizer_path"]

    print("\nEnvironment Variables Configured:")
    for k, v in paths.items():
        print(f"  - {k:16s}: {v}")

    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Google Colab Setup for NairaLLM V1.5")
    parser.add_argument("--dry-run", action="store_true", help="Inspect without mounting or launching")
    parser.add_argument("--no-drive", action="store_true", help="Skip Google Drive mounting")
    parser.add_argument("--run-pilot", action="store_true", help="Launch Semantic Pilot immediately after setup")
    args = parser.parse_args()

    paths = setup_colab_environment(dry_run=args.dry_run, mount_drive=not args.no_drive)

    if args.run_pilot and not args.dry_run:
        from NairaLLM.training.scripts.run_semantic_pilot import run_semantic_pilot
        run_semantic_pilot()


if __name__ == "__main__":
    main()
