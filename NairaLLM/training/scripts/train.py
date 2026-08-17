"""
Reproducible Training Pipeline for NairaLLM.

Supports:
- Resumable checkpointing
- Label masking (loss computed only on target completions)
- Learning rate scheduling with warmup and cosine decay
- Gradient clipping
- Validation evaluation loop
- Exporting trained checkpoint
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from NairaLLM.dataset.dataset_manager import DatasetManager
from NairaLLM.dataset.schemas.dataset_schema import NairaDatasetSample
from NairaLLM.model.architecture.naira_transformer import NairaTransformer
from NairaLLM.model.config.model_config import NairaModelConfig
from NairaLLM.model.tokenizer.naira_tokenizer import NairaTokenizer

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, Dataset
    _HAS_TORCH = True
except ImportError:
    _HAS_TORCH = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
_LOG = logging.getLogger("nairallm.train")


if _HAS_TORCH:

    class NairaDataset(Dataset):
        """PyTorch Dataset that formats multi-turn turns with label masking."""

        def __init__(
            self,
            samples: list[NairaDatasetSample],
            tokenizer: NairaTokenizer,
            max_seq_len: int = 512,
        ) -> None:
            self.tokenizer = tokenizer
            self.max_seq_len = max_seq_len
            self.items: list[tuple[torch.Tensor, torch.Tensor]] = []

            for sample in samples:
                self._process_sample(sample)

        def _process_sample(self, sample: NairaDatasetSample) -> None:
            # Build conversation string
            # Format: <|system|>\n{prompt}\n<|user|>\n{query}\n<|assistant|>\n{response}<|endoftext|>
            prompt_tokens: list[int] = []
            prompt_tokens.extend(self.tokenizer.encode(f"<|system|>\n{sample.system_prompt}\n"))

            input_ids: list[int] = list(prompt_tokens)
            labels: list[int] = [-100] * len(prompt_tokens)

            for msg in sample.conversations:
                if msg.role == "user":
                    user_str = f"<|user|>\n{msg.content}\n"
                    u_tokens = self.tokenizer.encode(user_str)
                    input_ids.extend(u_tokens)
                    labels.extend([-100] * len(u_tokens))
                elif msg.role == "tool":
                    tool_str = f"<|tool_result|>\n{msg.content}\n"
                    t_tokens = self.tokenizer.encode(tool_str)
                    input_ids.extend(t_tokens)
                    labels.extend([-100] * len(t_tokens))
                elif msg.role == "assistant":
                    asst_str = f"<|assistant|>\n{msg.content}<|endoftext|>\n"
                    a_tokens = self.tokenizer.encode(asst_str)
                    input_ids.extend(a_tokens)
                    # Assistant tokens are the targets for loss computation
                    labels.extend(a_tokens)

            if len(input_ids) > self.max_seq_len:
                input_ids = input_ids[: self.max_seq_len]
                labels = labels[: self.max_seq_len]

            self.items.append((torch.tensor(input_ids, dtype=torch.long), torch.tensor(labels, dtype=torch.long)))

        def __len__(self) -> int:
            return len(self.items)

        def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
            return self.items[idx]

    def collate_fn(
        batch: list[tuple[torch.Tensor, torch.Tensor]], pad_token_id: int = 0
    ) -> tuple[torch.Tensor, torch.Tensor]:
        input_ids_list, labels_list = zip(*batch)
        max_len = max(len(x) for x in input_ids_list)

        padded_inputs = []
        padded_labels = []

        for inp, lbl in zip(input_ids_list, labels_list):
            pad_len = max_len - len(inp)
            if pad_len > 0:
                padded_inp = torch.cat([inp, torch.full((pad_len,), pad_token_id, dtype=torch.long)])
                padded_lbl = torch.cat([lbl, torch.full((pad_len,), -100, dtype=torch.long)])
            else:
                padded_inp = inp
                padded_lbl = lbl
            padded_inputs.append(padded_inp)
            padded_labels.append(padded_lbl)

        return torch.stack(padded_inputs), torch.stack(padded_labels)


def get_lr_scheduler(optimizer: torch.optim.Optimizer, warmup_steps: int, total_steps: int, min_lr: float, max_lr: float):
    def lr_lambda(step: int) -> float:
        if step < warmup_steps:
            return float(step) / float(max(1, warmup_steps))
        progress = float(step - warmup_steps) / float(max(1, total_steps - warmup_steps))
        cosine_decay = 0.5 * (1.0 + math.cos(math.pi * progress))
        decayed = (min_lr + (max_lr - min_lr) * cosine_decay) / max_lr
        return max(min_lr / max_lr, decayed)

    return torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)


def train_model(config_path: str | Path, resume: bool = False, device: str = "cpu") -> Path:
    if not _HAS_TORCH:
        raise RuntimeError("PyTorch is required for training.")

    with open(config_path, "r", encoding="utf-8") as f:
        config_data = json.load(f)

    # Initialize tokenizer
    tokenizer_path = Path("NairaLLM/model/tokenizer/naira_tokenizer.json")
    tokenizer = NairaTokenizer(tokenizer_path)

    # Model configuration
    model_cfg_dict = config_data.get("model", {})
    model_cfg_dict["vocab_size"] = tokenizer.vocab_size
    model_config = NairaModelConfig.from_dict(model_cfg_dict)

    model = NairaTransformer(model_config).to(device)
    _LOG.info("Initialized NairaTransformer with %d parameters on %s", model.count_parameters(), device)

    # Dataset loading
    dm = DatasetManager()
    train_samples = dm.load_jsonl(dm.train_dir / "train.jsonl")
    val_samples = dm.load_jsonl(dm.val_dir / "val.jsonl")

    if not train_samples:
        # Fallback to reviewed if split not found
        train_samples = dm.load_jsonl(dm.reviewed_dir / "initial_dataset.jsonl")
        val_samples = train_samples[: max(1, len(train_samples) // 5)]

    train_dataset = NairaDataset(train_samples, tokenizer, max_seq_len=model_config.max_seq_len)
    val_dataset = NairaDataset(val_samples, tokenizer, max_seq_len=model_config.max_seq_len)

    train_cfg = config_data.get("training", {})
    batch_size = train_cfg.get("batch_size", 4)

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        collate_fn=lambda b: collate_fn(b, pad_token_id=tokenizer.pad_token_id),
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        collate_fn=lambda b: collate_fn(b, pad_token_id=tokenizer.pad_token_id),
    )

    # Optimizer & Scheduler
    lr = train_cfg.get("learning_rate", 5e-4)
    min_lr = train_cfg.get("min_learning_rate", 1e-5)
    weight_decay = train_cfg.get("weight_decay", 0.01)
    num_epochs = train_cfg.get("num_epochs", 30)
    warmup_steps = train_cfg.get("warmup_steps", 10)
    grad_clip = train_cfg.get("grad_clip", 1.0)
    checkpoint_dir = Path(train_cfg.get("checkpoint_dir", "NairaLLM/training/checkpoints"))
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    total_steps = len(train_loader) * num_epochs
    scheduler = get_lr_scheduler(optimizer, warmup_steps=warmup_steps, total_steps=total_steps, min_lr=min_lr, max_lr=lr)

    start_epoch = 0
    best_val_loss = float("inf")

    latest_ckpt_path = checkpoint_dir / "checkpoint_latest.pt"
    if resume and latest_ckpt_path.exists():
        ckpt = torch.load(str(latest_ckpt_path), map_location=device)
        model.load_state_dict(ckpt["model_state_dict"])
        optimizer.load_state_dict(ckpt["optimizer_state_dict"])
        start_epoch = ckpt.get("epoch", 0) + 1
        best_val_loss = ckpt.get("val_loss", float("inf"))
        _LOG.info("Resumed from checkpoint at epoch %d (best_val_loss=%.4f)", start_epoch, best_val_loss)

    _LOG.info("Starting training loop: %d epochs (%d steps total)...", num_epochs, total_steps)

    for epoch in range(start_epoch, num_epochs):
        model.train()
        total_train_loss = 0.0
        n_train_batches = 0

        for inputs, targets in train_loader:
            inputs = inputs.to(device)
            targets = targets.to(device)

            optimizer.zero_grad()
            _, loss, _ = model(inputs, targets=targets)

            if loss is not None:
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
                optimizer.step()
                scheduler.step()

                total_train_loss += loss.item()
                n_train_batches += 1

        avg_train_loss = total_train_loss / max(1, n_train_batches)

        # Validation
        model.eval()
        total_val_loss = 0.0
        n_val_batches = 0

        with torch.no_grad():
            for inputs, targets in val_loader:
                inputs = inputs.to(device)
                targets = targets.to(device)
                _, val_loss, _ = model(inputs, targets=targets)
                if val_loss is not None:
                    total_val_loss += val_loss.item()
                    n_val_batches += 1

        avg_val_loss = total_val_loss / max(1, n_val_batches)
        perplexity = math.exp(min(avg_val_loss, 20.0))

        _LOG.info(
            "Epoch %d/%d — Train Loss: %.4f | Val Loss: %.4f | Perplexity: %.2f | LR: %.6f",
            epoch + 1,
            num_epochs,
            avg_train_loss,
            avg_val_loss,
            perplexity,
            scheduler.get_last_lr()[0],
        )

        # Save latest checkpoint
        torch.save(
            {
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "train_loss": avg_train_loss,
                "val_loss": avg_val_loss,
                "config": model_config.to_dict(),
                "vocab_size": tokenizer.vocab_size,
            },
            str(latest_ckpt_path),
        )

        # Save best checkpoint
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            best_ckpt_path = checkpoint_dir / "checkpoint_best.pt"
            torch.save(
                {
                    "epoch": epoch,
                    "model_state_dict": model.state_dict(),
                    "val_loss": avg_val_loss,
                    "config": model_config.to_dict(),
                    "vocab_size": tokenizer.vocab_size,
                },
                str(best_ckpt_path),
            )
            _LOG.info("  * New best validation loss: %.4f (Saved to %s)", best_val_loss, best_ckpt_path.name)

    _LOG.info("Training completed. Best Val Loss: %.4f", best_val_loss)
    return checkpoint_dir / "checkpoint_best.pt"


def main() -> None:
    parser = argparse.ArgumentParser(description="Train NairaLLM Model")
    parser.add_argument("--config", type=str, default="NairaLLM/training/configs/prototype_config.json")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--device", type=str, default="cpu")
    args = parser.parse_args()

    train_model(config_path=args.config, resume=args.resume, device=args.device)


if __name__ == "__main__":
    main()
