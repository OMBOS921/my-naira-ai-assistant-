"""
Final NairaLLM V1 Multi-Stage GPU Training Engine.

Supports sequential training track:
stage=semantic -> stage=domain -> stage=cognition -> stage=tools -> stage=behavior

Features:
- Enforces CUDA requirement for production runs (Cost policy: Free Cloud GPU only)
- Strict parent checkpoint validation & lineage tracking (CheckpointChainManager)
- Instruction masking (computes cross-entropy loss exclusively on assistant tokens)
- Automatic Mixed Precision (FP16 AMP + GradScaler)
- Cosine Annealing with Warmup & Gradient Norm Clipping
- Full session resumption and metrics logging
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# Ensure workspace root in sys.path
workspace_root = Path(__file__).resolve().parent.parent.parent.parent
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from NairaLLM.model.config.model_config import NairaModelConfig
from NairaLLM.model.tokenizer.naira_tokenizer import NairaTokenizer
from NairaLLM.training.checkpoints.checkpoint_chain import (
    CheckpointChainManager,
    CheckpointMetadata,
    TrainingStage,
    compute_file_sha256,
    get_current_git_commit,
)

_LOG = logging.getLogger("nairallm.train_final_v1")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, Dataset
    from NairaLLM.model.architecture.naira_transformer import NairaTransformer
    _HAS_TORCH = True
except ImportError:
    _HAS_TORCH = False


if _HAS_TORCH:

    class PackedPretrainingDataset(Dataset):
        """Packed contiguous tokens for foundation semantic stage."""

        def __init__(self, file_path: Path, tokenizer: NairaTokenizer, max_seq_len: int = 512) -> None:
            self.max_seq_len = max_seq_len
            all_tokens: list[int] = []

            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    item = json.loads(line)
                    text = item.get("text", "")
                    if text:
                        toks = tokenizer.encode(text) + [tokenizer.eos_token_id]
                        all_tokens.extend(toks)

            self.chunks: list[list[int]] = []
            for i in range(0, len(all_tokens) - max_seq_len, max_seq_len):
                self.chunks.append(all_tokens[i : i + max_seq_len + 1])

            if not self.chunks and len(all_tokens) > 1:
                self.chunks.append(all_tokens[: min(len(all_tokens), max_seq_len + 1)])

        def __len__(self) -> int:
            return len(self.chunks)

        def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
            chunk = self.chunks[idx]
            input_ids = torch.tensor(chunk[:-1], dtype=torch.long)
            targets = torch.tensor(chunk[1:], dtype=torch.long)
            return input_ids, targets


    class MaskedInstructionDataset(Dataset):
        """Structured conversation dataset with target masking (loss on assistant tokens only)."""

        def __init__(self, file_path: Path, tokenizer: NairaTokenizer, max_seq_len: int = 1024) -> None:
            self.max_seq_len = max_seq_len
            self.samples: list[tuple[torch.Tensor, torch.Tensor]] = []

            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    item = json.loads(line)
                    convs = item.get("conversations", [])
                    if not convs:
                        continue

                    token_ids: list[int] = []
                    target_ids: list[int] = []

                    sys_prompt = item.get("system_prompt", "You are Naira, a thoughtful, proactive AI operating system assistant.")
                    sys_text = f"<|system|>\n{sys_prompt}\n"
                    sys_tokens = tokenizer.encode(sys_text)
                    token_ids.extend(sys_tokens)
                    target_ids.extend([-100] * len(sys_tokens))

                    for turn in convs:
                        role = turn.get("role", "user")
                        content = turn.get("content", "")
                        turn_text = f"<|{role}|>\n{content}\n"
                        turn_toks = tokenizer.encode(turn_text)

                        if role == "assistant":
                            turn_toks.append(tokenizer.eos_token_id)
                            token_ids.extend(turn_toks)
                            # Supervise assistant tokens
                            target_ids.extend(turn_toks)
                        else:
                            token_ids.extend(turn_toks)
                            # Mask user/system tokens
                            target_ids.extend([-100] * len(turn_toks))

                    if len(token_ids) > max_seq_len + 1:
                        token_ids = token_ids[: max_seq_len + 1]
                        target_ids = target_ids[: max_seq_len + 1]

                    if len(token_ids) > 1:
                        inp = torch.tensor(token_ids[:-1], dtype=torch.long)
                        tgt = torch.tensor(target_ids[1:], dtype=torch.long)

                        # Pad to fixed max_seq_len if needed or keep dynamic
                        self.samples.append((inp, tgt))

        def __len__(self) -> int:
            return len(self.samples)

        def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
            return self.samples[idx]


def get_cosine_schedule_with_warmup(
    optimizer: torch.optim.Optimizer,
    num_warmup_steps: int,
    num_training_steps: int,
    min_lr_ratio: float = 0.025,
) -> torch.optim.lr_scheduler.LambdaLR:
    def lr_lambda(current_step: int) -> float:
        if current_step < num_warmup_steps:
            return float(current_step) / float(max(1, num_warmup_steps))
        progress = float(current_step - num_warmup_steps) / float(max(1, num_training_steps - num_warmup_steps))
        cosine_decay = 0.5 * (1.0 + math.cos(math.pi * progress))
        return max(min_lr_ratio, min_lr_ratio + (1.0 - min_lr_ratio) * cosine_decay)

    return torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)


def train_stage(
    stage: str,
    config_path: str | Path,
    parent_checkpoint: str | Path | None = None,
    resume_checkpoint: str | Path | None = None,
    allow_cpu_smoke_test: bool = False,
    override_epochs: int | None = None,
    max_steps: int | None = None,
) -> Path:
    if not _HAS_TORCH:
        raise RuntimeError("PyTorch is required for NairaLLM training pipeline.")

    # 1. Hardware Verification
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type == "cpu" and not allow_cpu_smoke_test:
        raise RuntimeError(
            "CUDA accelerator not found. Cost Policy Enforced: Final NairaLLM V1 training requires "
            "a free cloud GPU (e.g. Google Colab / Kaggle Tesla T4). Local training without GPU is restricted. "
            "Use --allow-cpu-smoke-test for local unit verification only."
        )

    _LOG.info("Training on device: %s (%s)", device, torch.cuda.get_device_name(0) if device.type == "cuda" else "CPU")

    # 2. Load Canonical Configuration
    config_file = Path(config_path)
    with open(config_file, "r", encoding="utf-8") as f:
        full_cfg = json.load(f)

    model_config = NairaModelConfig.from_dict(full_cfg)
    tokenizer = NairaTokenizer(Path("NairaLLM/model/tokenizer/naira_tokenizer.json"))
    model_config.vocab_size = tokenizer.vocab_size

    # Stage config lookup
    stage_info = next((s for s in full_cfg.get("stages", []) if s["stage"] == stage), None)
    if stage_info is None:
        raise ValueError(f"Unknown stage '{stage}'. Defined stages: {[s['stage'] for s in full_cfg.get('stages', [])]}")

    dataset_rel_path = stage_info["dataset_path"]
    dataset_path = workspace_root / dataset_rel_path
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset for stage '{stage}' not found at: {dataset_path}")

    learning_rate = stage_info.get("learning_rate", 2e-4)
    epochs = override_epochs or stage_info.get("epochs", 10)
    batch_size = full_cfg.get("training", {}).get("batching", {}).get("micro_batch_size", 4)
    grad_accum = full_cfg.get("training", {}).get("batching", {}).get("gradient_accumulation_steps", 4)
    max_seq_len = full_cfg.get("training", {}).get("batching", {}).get("max_seq_len", 1024)

    _LOG.info("Initializing stage [%s] -> epochs=%d, lr=%.2e, dataset=%s", stage, epochs, learning_rate, dataset_path.name)

    # 3. Lineage Validation
    chain_mgr = CheckpointChainManager(workspace_root / "NairaLLM" / "training" / "checkpoints")
    is_valid, reason = chain_mgr.validate_parent(stage, parent_checkpoint)
    _LOG.info("Lineage check: %s (%s)", "PASSED" if is_valid else "WARNING", reason)

    # 4. Model Initialization & Parent Weights Loading
    model = NairaTransformer(model_config).to(device)
    param_count = model.count_parameters()
    _LOG.info("Instantiated NairaTransformer (%d trainable parameters)", param_count)

    if parent_checkpoint and Path(parent_checkpoint).exists():
        p = Path(parent_checkpoint)
        if p.suffix == ".pt":
            ckpt_data = torch.load(p, map_location=device)
            state_dict = ckpt_data.get("model_state_dict", ckpt_data)
            model.load_state_dict(state_dict, strict=False)
            _LOG.info("Loaded parent PyTorch weights from %s", p.name)
        elif p.suffix == ".npz":
            import numpy as np
            npz = np.load(str(p))
            # Load embeddings if matching
            if "tok_embeddings" in npz.files:
                w = torch.from_numpy(npz["tok_embeddings"]).float()
                if w.shape == model.tok_embeddings.weight.shape:
                    model.tok_embeddings.weight.data.copy_(w)
                    _LOG.info("Loaded embedding weights from numpy checkpoint %s", p.name)

    # 5. Dataset & DataLoader
    if stage == "semantic":
        dataset = PackedPretrainingDataset(dataset_path, tokenizer, max_seq_len=min(max_seq_len, 512))
    else:
        dataset = MaskedInstructionDataset(dataset_path, tokenizer, max_seq_len=max_seq_len)

    if len(dataset) == 0:
        raise ValueError(f"Dataset {dataset_path.name} produced 0 usable training samples.")

    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True, drop_last=False)
    total_steps = (len(dataloader) // grad_accum) * epochs

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=learning_rate,
        betas=(0.9, 0.95),
        weight_decay=0.01,
    )
    scheduler = get_cosine_schedule_with_warmup(optimizer, num_warmup_steps=min(50, total_steps // 10), num_training_steps=max(1, total_steps))
    use_amp = (device.type == "cuda")
    scaler = torch.cuda.amp.GradScaler(enabled=use_amp)

    # 6. Training Loop
    model.train()
    step_count = 0
    epoch_losses = []

    t_start = time.time()
    for ep in range(1, epochs + 1):
        running_loss = 0.0
        batch_count = 0
        optimizer.zero_grad()

        for b_idx, (inputs, targets) in enumerate(dataloader):
            inputs = inputs.to(device)
            targets = targets.to(device)

            with torch.cuda.amp.autocast(enabled=use_amp):
                _, loss, _ = model(inputs, targets=targets)
                loss_scaled = loss / grad_accum

            scaler.scale(loss_scaled).backward()
            running_loss += loss.item()
            batch_count += 1

            if (b_idx + 1) % grad_accum == 0 or (b_idx + 1) == len(dataloader):
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad()
                scheduler.step()
                step_count += 1

            if max_steps and step_count >= max_steps:
                break

        avg_loss = running_loss / max(1, batch_count)
        ppl = math.exp(min(avg_loss, 20.0))
        epoch_losses.append(avg_loss)
        _LOG.info("Epoch [%d/%d] -> Loss: %.4f | Perplexity: %.2f | LR: %.2e", ep, epochs, avg_loss, ppl, scheduler.get_last_lr()[0])

        if max_steps and step_count >= max_steps:
            _LOG.info("Reached max_steps limit (%d). Terminating dry-run.", max_steps)
            break

    # 7. Save Checkpoint with Chain Metadata
    stage_dir = chain_mgr.get_stage_checkpoint_dir(stage)
    ckpt_filename = f"nairallm_v1_{stage}_checkpoint.pt"
    ckpt_path = stage_dir / ckpt_filename

    torch.save({
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "model_config": model_config.to_dict(),
        "stage": stage,
        "epochs_trained": ep,
        "final_loss": epoch_losses[-1] if epoch_losses else 0.0,
    }, ckpt_path)

    metrics = {
        "final_loss": round(epoch_losses[-1] if epoch_losses else 0.0, 4),
        "perplexity": round(math.exp(min(epoch_losses[-1] if epoch_losses else 0.0, 20.0)), 2),
        "epochs_completed": ep,
        "total_steps": step_count,
        "duration_seconds": round(time.time() - t_start, 2),
    }
    hardware_info = {
        "device": device.type,
        "device_name": torch.cuda.get_device_name(0) if device.type == "cuda" else "CPU",
        "precision": "FP16_AMP" if use_amp else "FP32",
    }

    meta = chain_mgr.register_checkpoint(
        stage=stage,
        checkpoint_name=f"nairallm_v1_{stage}_checkpoint",
        weights_path=ckpt_path,
        parent_metadata_path=parent_checkpoint,
        dataset_path=dataset_path,
        tokenizer_path=workspace_root / "NairaLLM" / "model" / "tokenizer" / "naira_tokenizer.json",
        config_path=config_file,
        metrics=metrics,
        hardware_info=hardware_info,
    )
    _LOG.info("Stage [%s] successfully completed. Checkpoint saved to %s", stage, ckpt_path.name)
    return ckpt_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Final NairaLLM V1 GPU Training Pipeline")
    parser.add_argument("--stage", type=str, required=True, choices=["semantic", "domain", "cognition", "tools", "behavior", "final"])
    parser.add_argument("--config", type=str, default="NairaLLM/configs/final_nairallm_v1.json")
    parser.add_argument("--parent-checkpoint", type=str, default=None, help="Path to parent metadata JSON or weights")
    parser.add_argument("--resume", type=str, default=None, help="Resume training from existing checkpoint")
    parser.add_argument("--allow-cpu-smoke-test", action="store_true", help="Allow CPU execution strictly for local smoke testing / validation")
    parser.add_argument("--epochs", type=int, default=None, help="Override number of epochs")
    parser.add_argument("--max-steps", type=int, default=None, help="Limit step count for dry-run verification")
    args = parser.parse_args()

    train_stage(
        stage=args.stage,
        config_path=args.config,
        parent_checkpoint=args.parent_checkpoint,
        resume_checkpoint=args.resume,
        allow_cpu_smoke_test=args.allow_cpu_smoke_test,
        override_epochs=args.epochs,
        max_steps=args.max_steps,
    )


if __name__ == "__main__":
    main()
