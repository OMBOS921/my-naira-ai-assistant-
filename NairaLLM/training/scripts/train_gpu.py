"""
PyTorch GPU Training Engine for NairaLLM V1.5 Semantic Pretraining.

Features:
- Dynamic Hardware Detection (CUDA, MPS, CPU)
- Automatic Mixed Precision (AMP with GradScaler)
- Gradient Accumulation for Effective Batch Sizing on Free Cloud Tiers
- Cosine Annealing Learning Rate Schedule with Warmup
- Gradient Norm Clipping
- Comprehensive State Checkpointing (.pt + optimizer + scheduler + metadata)
- Real-time Perplexity & Validation Monitoring
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
from NairaLLM.training.cloud.check_environment import (
    USE_PAID_COMPUTE,
    inspect_environment,
    print_diagnostic_report,
    verify_free_gpu_or_stop,
)

_LOG = logging.getLogger("nairallm.train_gpu")

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
        """Packed contiguous token sequences for efficient language model pretraining."""

        def __init__(
            self,
            samples: list[dict[str, Any]],
            tokenizer: NairaTokenizer,
            max_seq_len: int = 512,
        ) -> None:
            self.max_seq_len = max_seq_len
            all_tokens: list[int] = []

            for s in samples:
                text = s.get("text", "")
                if not text:
                    continue
                tokens = tokenizer.encode(text) + [tokenizer.eos_token_id]
                all_tokens.extend(tokens)

            # Chunk into fixed max_seq_len blocks
            self.chunks: list[list[int]] = []
            for i in range(0, len(all_tokens) - max_seq_len, max_seq_len):
                self.chunks.append(all_tokens[i : i + max_seq_len + 1])

            if not self.chunks and len(all_tokens) > 1:
                # Handle small datasets gracefully
                self.chunks.append(all_tokens[: min(len(all_tokens), max_seq_len + 1)])

        def __len__(self) -> int:
            return len(self.chunks)

        def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
            chunk = self.chunks[idx]
            input_ids = torch.tensor(chunk[:-1], dtype=torch.long)
            targets = torch.tensor(chunk[1:], dtype=torch.long)
            return input_ids, targets


def get_git_commit_sha() -> str:
    """Returns the current Git commit SHA."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(workspace_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return os.environ.get("GIT_COMMIT_SHA", "unknown")


def get_git_branch() -> str:
    """Returns the active Git branch."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(workspace_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return os.environ.get("GIT_BRANCH", "main")


def compute_file_sha256(file_path: Path) -> str:
    """Computes SHA-256 hash of a file."""
    if not file_path.exists():
        return "not_found"
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def load_dataset_samples(dataset_path: str | Path) -> list[dict[str, Any]]:
    path = Path(dataset_path)
    if not path.exists():
        # Fallback to build script
        from NairaLLM.dataset.build_semantic_corpus import main as build_corpus
        build_corpus()

    samples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    samples.append(json.loads(line))
                except Exception:
                    pass
    return samples


def train_gpu(
    dataset_path: str | Path | None = None,
    checkpoint_dir: str | Path | None = None,
    epochs: int = 25,
    batch_size: int = 4,
    grad_accum_steps: int = 4,
    learning_rate: float = 4e-4,
    max_seq_len: int = 256,
    d_model: int = 128,
    num_layers: int = 4,
    num_heads: int = 4,
    d_ff: int = 512,
    resume: bool = False,
    require_free_gpu: bool = True,
    allow_cpu_fallback: bool = False,
) -> dict[str, Any]:
    print("==================================================")
    print("    NAIRALLM V1.5 — FREE CLOUD GPU TRAINER        ")
    print("==================================================")

    env = inspect_environment()
    print_diagnostic_report(env)

    # Cost Guard and Free GPU Enforcement
    if not allow_cpu_fallback and require_free_gpu:
        if not _HAS_TORCH or not env.get("cuda_available", False):
            verify_free_gpu_or_stop(require_gpu=True)

    if not _HAS_TORCH:
        if allow_cpu_fallback:
            print("[NOTICE] Running in Pure-NumPy CPU verification mode as explicitly permitted.")
            from NairaLLM.training.scripts.train_v1_4_structured_model import train_v1_4_structured_model
            return train_v1_4_structured_model(epochs=epochs)
        else:
            raise RuntimeError("Free Cloud GPU is required for heavy training runs.")

    # 1. Device Selection
    if torch.cuda.is_available():
        device = torch.device("cuda")
        device_name = torch.cuda.get_device_name(0)
        use_amp = True
        print(f"[DEVICE] Accelerated CUDA GPU: {device_name}")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = torch.device("mps")
        device_name = "Apple Silicon MPS"
        use_amp = False
        print(f"[DEVICE] Apple Silicon MPS: {device_name}")
    else:
        device = torch.device("cpu")
        device_name = "Host CPU"
        use_amp = False
        print(f"[DEVICE] Host CPU: {device_name}")

    # 2. Tokenizer & Dataset
    tok_path = Path(os.environ.get("NAIRA_TOKENIZER_PATH", "NairaLLM/model/tokenizer/naira_tokenizer.json"))
    tokenizer = NairaTokenizer(tok_path)
    print(f"[TOKENIZER] Loaded NairaTokenizer (Vocab Size = {tokenizer.vocab_size})")

    ds_path = Path(dataset_path or os.environ.get("NAIRA_DATASET_PATH", "NairaLLM/dataset/semantic_corpus/semantic_pretrain_v1_5_expanded.jsonl"))
    if not ds_path.exists():
        ds_path = Path("NairaLLM/dataset/semantic_corpus/semantic_pretrain_v1_5.jsonl")
    samples = load_dataset_samples(ds_path)
    ds_sha256 = compute_file_sha256(ds_path)
    git_sha = get_git_commit_sha()
    git_branch = get_git_branch()

    print(f"[SOURCE CONTROL] Git Commit:    {git_sha}")
    print(f"[SOURCE CONTROL] Git Branch:    {git_branch}")
    print(f"[DATASET] Loaded {len(samples)} pretraining samples from {ds_path.name}")
    print(f"[DATASET] SHA-256:              {ds_sha256}")

    # Split 90% train / 10% val
    n_train = max(1, int(len(samples) * 0.9))
    train_samples = samples[:n_train]
    val_samples = samples[n_train:] or samples[:1]

    train_ds = PackedPretrainingDataset(train_samples, tokenizer, max_seq_len=max_seq_len)
    val_ds = PackedPretrainingDataset(val_samples, tokenizer, max_seq_len=max_seq_len)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, drop_last=False)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)

    print(f"[CHUNKS] Packed into {len(train_ds)} train blocks and {len(val_ds)} val blocks (Context={max_seq_len})")

    # 3. Model Configuration & Initialization
    config = NairaModelConfig(
        vocab_size=tokenizer.vocab_size,
        d_model=d_model,
        num_layers=num_layers,
        num_heads=num_heads,
        num_kv_heads=num_heads,
        d_ff=d_ff,
        max_seq_len=max_seq_len,
    )
    model = NairaTransformer(config).to(device)
    param_count = model.count_parameters()
    print(f"[MODEL] Initialized NairaTransformer ({param_count:,} parameters)")
    print(f"[CONFIG] {config.to_dict()}")

    # 4. Optimizer, Scheduler & Scaler
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=0.01, betas=(0.9, 0.95))
    total_steps = max(1, (len(train_loader) // grad_accum_steps) * epochs)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=total_steps, eta_min=1e-5)
    scaler = torch.cuda.amp.GradScaler(enabled=use_amp and device.type == "cuda")

    ckpt_dir = Path(checkpoint_dir or os.environ.get("NAIRA_CHECKPOINT_DIR", "NairaLLM/training/checkpoints"))
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    start_epoch = 1
    global_step = 0
    best_val_loss = float("inf")

    # Resume handling
    if resume:
        latest_ckpt = ckpt_dir / "naira_model_v1_5_latest.pt"
        if latest_ckpt.exists():
            print(f"[RESUME] Loading checkpoint from {latest_ckpt}")
            ckpt_data = torch.load(latest_ckpt, map_location=device)
            model.load_state_dict(ckpt_data["model_state_dict"])
            optimizer.load_state_dict(ckpt_data["optimizer_state_dict"])
            if "scheduler_state_dict" in ckpt_data:
                scheduler.load_state_dict(ckpt_data["scheduler_state_dict"])
            start_epoch = ckpt_data.get("epoch", 1) + 1
            global_step = ckpt_data.get("global_step", 0)
            best_val_loss = ckpt_data.get("best_val_loss", float("inf"))
            print(f"[RESUME] Resuming from Epoch {start_epoch}, Step {global_step}")

    history: dict[str, list[Any]] = {
        "train_loss": [],
        "val_loss": [],
        "val_ppl": [],
        "epochs": [],
    }

    print("\nStarting Training Loop...")
    start_time = time.perf_counter()

    for epoch in range(start_epoch, epochs + 1):
        model.train()
        epoch_loss = 0.0
        step_count = 0
        optimizer.zero_grad(set_to_none=True)

        for b_idx, (x, y) in enumerate(train_loader):
            x = x.to(device, non_blocking=True)
            y = y.to(device, non_blocking=True)

            with torch.cuda.amp.autocast(enabled=use_amp and device.type == "cuda"):
                logits, loss, _ = model(x, targets=y)
                loss_scaled = loss / grad_accum_steps

            scaler.scale(loss_scaled).backward()
            epoch_loss += loss.item()
            step_count += 1

            if (b_idx + 1) % grad_accum_steps == 0 or (b_idx + 1) == len(train_loader):
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad(set_to_none=True)
                scheduler.step()
                global_step += 1

        avg_train_loss = epoch_loss / max(1, step_count)

        # Validation
        model.eval()
        val_loss_total = 0.0
        val_steps = 0
        with torch.no_grad():
            for x_v, y_v in val_loader:
                x_v = x_v.to(device, non_blocking=True)
                y_v = y_v.to(device, non_blocking=True)
                with torch.cuda.amp.autocast(enabled=use_amp and device.type == "cuda"):
                    _, v_loss, _ = model(x_v, targets=y_v)
                val_loss_total += v_loss.item()
                val_steps += 1

        avg_val_loss = val_loss_total / max(1, val_steps)
        val_ppl = math.exp(min(avg_val_loss, 20.0))

        history["epochs"].append(epoch)
        history["train_loss"].append(round(avg_train_loss, 4))
        history["val_loss"].append(round(avg_val_loss, 4))
        history["val_ppl"].append(round(val_ppl, 2))

        print(f"Epoch {epoch:02d}/{epochs:02d} | Train Loss: {avg_train_loss:.4f} | Val Loss: {avg_val_loss:.4f} (PPL: {val_ppl:.2f})")

        # Save latest checkpoint
        latest_path = ckpt_dir / "naira_model_v1_5_latest.pt"
        checkpoint_payload = {
            "epoch": epoch,
            "global_step": global_step,
            "step": global_step,
            "git_commit_sha": git_sha,
            "git_branch": git_branch,
            "dataset_version": ds_path.name,
            "dataset_sha256": ds_sha256,
            "tokenizer_vocab_size": tokenizer.vocab_size,
            "model_config": config.to_dict(),
            "training_config": {
                "epochs": epochs,
                "batch_size": batch_size,
                "gradient_accumulation_steps": grad_accum_steps,
                "learning_rate": learning_rate,
                "max_seq_len": max_seq_len,
            },
            "metrics": {
                "train_loss": avg_train_loss,
                "val_loss": avg_val_loss,
                "val_perplexity": val_ppl,
                "best_val_loss": min(best_val_loss, avg_val_loss),
            },
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "scheduler_state_dict": scheduler.state_dict(),
            "train_loss": avg_train_loss,
            "val_loss": avg_val_loss,
            "best_val_loss": min(best_val_loss, avg_val_loss),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        torch.save(checkpoint_payload, str(latest_path))

        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            best_path = ckpt_dir / "naira_model_v1_5_best.pt"
            torch.save(checkpoint_payload, str(best_path))

    total_time = time.perf_counter() - start_time
    print(f"\n[DONE] Training complete in {total_time:.2f}s ({total_time/60:.2f} min)")

    # Save metadata JSON
    meta_path = ckpt_dir / "naira_model_v1_5_metadata.json"
    metadata = {
        "version": "1.5",
        "description": "NairaLLM V1.5 Semantic Pretrained Foundation",
        "git_commit_sha": git_sha,
        "git_branch": git_branch,
        "dataset_version": ds_path.name,
        "dataset_sha256": ds_sha256,
        "tokenizer_vocab_size": tokenizer.vocab_size,
        "device_used": device_name,
        "model_config": config.to_dict(),
        "training_config": {
            "epochs": epochs,
            "batch_size": batch_size,
            "gradient_accumulation_steps": grad_accum_steps,
            "learning_rate": learning_rate,
            "max_seq_len": max_seq_len,
        },
        "total_parameters": param_count,
        "epochs": epochs,
        "final_train_loss": history["train_loss"][-1] if history["train_loss"] else None,
        "final_val_loss": history["val_loss"][-1] if history["val_loss"] else None,
        "best_val_loss": round(best_val_loss, 4),
        "metrics": {
            "final_train_loss": history["train_loss"][-1] if history["train_loss"] else None,
            "final_val_loss": history["val_loss"][-1] if history["val_loss"] else None,
            "best_val_loss": round(best_val_loss, 4),
            "total_time_seconds": round(total_time, 2),
        },
        "history": history,
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"[CHECKPOINTS SAVED] in {ckpt_dir}:")
    print(f"  - naira_model_v1_5_latest.pt")
    print(f"  - naira_model_v1_5_best.pt")
    print(f"  - naira_model_v1_5_metadata.json")

    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="NairaLLM V1.5 PyTorch GPU Pretrainer")
    parser.add_argument("--epochs", type=int, default=25, help="Number of epochs")
    parser.add_argument("--batch-size", type=int, default=4, help="Per-device batch size")
    parser.add_argument("--grad-accum", type=int, default=4, help="Gradient accumulation steps")
    parser.add_argument("--lr", type=float, default=4e-4, help="Initial learning rate")
    parser.add_argument("--max-seq-len", type=int, default=256, help="Maximum context length")
    parser.add_argument("--d-model", type=int, default=128, help="Hidden dimension")
    parser.add_argument("--layers", type=int, default=4, help="Number of transformer layers")
    parser.add_argument("--heads", type=int, default=4, help="Number of attention heads")
    parser.add_argument("--d-ff", type=int, default=512, help="Feed-forward dimension")
    parser.add_argument("--dataset-path", type=str, default=None, help="Path to pretraining JSONL")
    parser.add_argument("--checkpoint-dir", type=str, default=None, help="Directory to save checkpoints")
    parser.add_argument("--resume", action="store_true", help="Resume from latest checkpoint")
    parser.add_argument("--allow-cpu-fallback", action="store_true", help="Explicitly allow local CPU fallback for debug verification")
    args = parser.parse_args()

    train_gpu(
        dataset_path=args.dataset_path,
        checkpoint_dir=args.checkpoint_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        grad_accum_steps=args.grad_accum,
        learning_rate=args.lr,
        max_seq_len=args.max_seq_len,
        d_model=args.d_model,
        num_layers=args.layers,
        num_heads=args.heads,
        d_ff=args.d_ff,
        resume=args.resume,
        allow_cpu_fallback=args.allow_cpu_fallback,
    )


if __name__ == "__main__":
    main()
