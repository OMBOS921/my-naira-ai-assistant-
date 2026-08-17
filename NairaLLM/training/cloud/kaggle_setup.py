"""
Kaggle Notebooks Automated Setup & Pretraining Orchestration Script for NairaLLM V1.5.

Handles:
- Dynamic GPU detection (P100 / 2x T4)
- Working directory and persistent export path configuration (`/kaggle/working/checkpoints`)
- Dataset locator
- Automated packaging of checkpoints for local download
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

# Ensure workspace root in sys.path
workspace_root = Path(__file__).resolve().parent.parent.parent.parent
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

from NairaLLM.training.cloud.check_environment import inspect_environment, print_diagnostic_report


def setup_kaggle_environment(dry_run: bool = False) -> dict[str, str]:
    print("==================================================")
    print("    NAIRALLM — KAGGLE NOTEBOOKS TRAINING SETUP    ")
    print("==================================================")

    env = inspect_environment()
    print_diagnostic_report(env)

    paths: dict[str, str] = {}
    is_kaggle = os.path.exists("/kaggle") or "KAGGLE_KERNEL_RUN_TYPE" in os.environ

    if is_kaggle:
        print("[DETECTED] Running inside Kaggle Notebook environment.")
        working_dir = Path("/kaggle/working/NairaLLM")
        ckpt_dir = working_dir / "checkpoints"
        ckpt_dir.mkdir(parents=True, exist_ok=True)
        paths["checkpoint_dir"] = str(ckpt_dir)
        paths["working_dir"] = str(working_dir)
        print(f"[STORAGE] Kaggle exportable checkpoint directory: {ckpt_dir}")
    else:
        print("[LOCAL / SIMULATION] Running outside Kaggle.")
        local_dir = workspace_root / "NairaLLM" / "training" / "checkpoints"
        local_dir.mkdir(parents=True, exist_ok=True)
        paths["checkpoint_dir"] = str(local_dir)
        paths["working_dir"] = str(workspace_root)

    paths["dataset_path"] = str(workspace_root / "NairaLLM" / "dataset" / "semantic_corpus" / "semantic_pretrain_v1_5.jsonl")
    paths["tokenizer_path"] = str(workspace_root / "NairaLLM" / "model" / "tokenizer" / "naira_tokenizer.json")

    os.environ["NAIRA_CHECKPOINT_DIR"] = paths["checkpoint_dir"]
    os.environ["NAIRA_DATASET_PATH"] = paths["dataset_path"]
    os.environ["NAIRA_TOKENIZER_PATH"] = paths["tokenizer_path"]

    print("\nEnvironment Variables Configured:")
    for k, v in paths.items():
        print(f"  - {k:16s}: {v}")

    return paths


def package_checkpoints_for_download(checkpoint_dir: str | Path, output_zip: str | Path | None = None) -> str:
    """Create a zip archive of checkpoints for convenient Kaggle browser download."""
    ckpt_path = Path(checkpoint_dir)
    if not ckpt_path.exists():
        print(f"[ERROR] Checkpoint directory {ckpt_path} does not exist.")
        return ""

    if output_zip is None:
        output_zip = ckpt_path.parent / "nairallm_v1_5_checkpoints"

    zip_path = shutil.make_archive(str(output_zip), "zip", str(ckpt_path))
    print(f"[PACKAGED] Created downloadable archive at: {zip_path}")
    return zip_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Kaggle Notebooks Setup for NairaLLM V1.5")
    parser.add_argument("--dry-run", action="store_true", help="Inspect without modifying directories")
    parser.add_argument("--package-only", action="store_true", help="Package existing checkpoints to zip")
    parser.add_argument("--run-training", action="store_true", help="Launch GPU training immediately")
    args = parser.parse_args()

    paths = setup_kaggle_environment(dry_run=args.dry_run)

    if args.package_only:
        package_checkpoints_for_download(paths["checkpoint_dir"])
    elif args.run_training and not args.dry_run:
        from NairaLLM.training.scripts.train_gpu import main as run_train
        run_train()
        package_checkpoints_for_download(paths["checkpoint_dir"])


if __name__ == "__main__":
    main()
