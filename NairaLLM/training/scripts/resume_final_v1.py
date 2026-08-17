"""
Resume Runner for Final NairaLLM V1 GPU Training Track.

Convenience wrapper around `train_final_v1.py` to resume interrupted training sessions.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure workspace root in sys.path
workspace_root = Path(__file__).resolve().parent.parent.parent.parent
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

from NairaLLM.training.scripts.train_final_v1 import train_stage


def main() -> None:
    parser = argparse.ArgumentParser(description="Resume Final NairaLLM V1 GPU Training Session")
    parser.add_argument("--stage", type=str, required=True, choices=["semantic", "domain", "cognition", "tools", "behavior", "final"])
    parser.add_argument("--resume-checkpoint", type=str, required=True, help="Path to checkpoint .pt to resume from")
    parser.add_argument("--config", type=str, default="NairaLLM/configs/final_nairallm_v1.json")
    parser.add_argument("--allow-cpu-smoke-test", action="store_true", help="Allow CPU execution strictly for local smoke test")
    parser.add_argument("--epochs", type=int, default=None, help="Override number of epochs")
    args = parser.parse_args()

    train_stage(
        stage=args.stage,
        config_path=args.config,
        resume_checkpoint=args.resume_checkpoint,
        allow_cpu_smoke_test=args.allow_cpu_smoke_test,
        override_epochs=args.epochs,
    )


if __name__ == "__main__":
    main()
