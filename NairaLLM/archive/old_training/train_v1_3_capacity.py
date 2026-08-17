"""
NairaLLM V1.3 Capacity Scaling Training Pipeline.

Trains models across capacity scales with exact parity:
- Experiment B (Small Scale): d_model=128, layers=4, heads=4, d_ff=512
- Experiment C (Medium Scale): d_model=256, layers=6, heads=8, d_ff=1024

Controls:
- Same Byte-Level BPE Tokenizer (1507 vocab)
- Same Dataset (v1_1_expanded_dataset.jsonl, 561 samples)
- Same 80/10/10 Train/Val/Test Split (seed=42)
- Same Target-Only Instruction Masking
- Same Adam Optimizer + Cosine Schedule (20 epochs)
"""

from __future__ import annotations

import json
import logging
import math
import os
import sys
import time
from pathlib import Path
from typing import Any
import numpy as np

# Ensure workspace root is in sys.path
workspace_root = Path(__file__).resolve().parent.parent.parent.parent
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from NairaLLM.dataset.dataset_manager import DatasetManager
from NairaLLM.model.config.model_config import NairaModelConfig
from NairaLLM.model.runtime.numpy_backend import (
    NumpyNairaModel,
    apply_rope_np,
    rms_norm,
)
from NairaLLM.model.tokenizer.naira_tokenizer import NairaTokenizer

_LOG = logging.getLogger("nairallm.train_v1_3")


def softmax_np(x: np.ndarray, axis: int = -1) -> np.ndarray:
    e_x = np.exp(x - np.max(x, axis=axis, keepdims=True))
    return e_x / np.sum(e_x, axis=axis, keepdims=True)


def silu(x: np.ndarray) -> np.ndarray:
    return x / (1.0 + np.exp(-np.clip(x, -30.0, 30.0)))


def d_silu(x: np.ndarray) -> np.ndarray:
    s = 1.0 / (1.0 + np.exp(-np.clip(x, -30.0, 30.0)))
    return s * (1.0 + x * (1.0 - s))


def format_dataset_with_instruction_mask(
    samples: list[Any],
    tokenizer: NairaTokenizer,
    max_seq_len: int = 256,
) -> list[tuple[list[int], np.ndarray]]:
    """Construct sequence and target mask where prompt tokens = 0.0 and assistant response tokens = 1.0."""
    sequences = []
    for s in samples:
        prompt_str = f"<|system|>\n{s.system_prompt}\n"
        for msg in s.conversations[:-1]:
            if msg.role == "user":
                prompt_str += f"<|user|>\n{msg.content}\n"
            elif msg.role == "tool":
                prompt_str += f"<|tool_result|>\n{msg.content}\n"
            elif msg.role == "assistant":
                prompt_str += f"<|assistant|>\n{msg.content}<|endoftext|>\n"

        last_msg = s.conversations[-1]
        prompt_str += "<|assistant|>\n"
        target_str = f"{last_msg.content}<|endoftext|>\n"

        prompt_tokens = tokenizer.encode(prompt_str)
        target_tokens = tokenizer.encode(target_str)

        all_tokens = (prompt_tokens + target_tokens)[:max_seq_len]
        if len(all_tokens) < 2:
            continue

        mask = np.zeros(len(all_tokens) - 1, dtype=np.float32)
        target_start = max(0, len(prompt_tokens) - 1)
        mask[target_start:] = 1.0

        if np.sum(mask) > 0:
            sequences.append((all_tokens, mask))

    return sequences


def evaluate_masked_val_loss(
    model: NumpyNairaModel,
    val_sequences: list[tuple[list[int], np.ndarray]],
) -> tuple[float, float]:
    """Evaluate loss and perplexity on masked target tokens of validation set."""
    if not val_sequences:
        return 0.0, 1.0
    total_val_loss = 0.0
    total_val_tokens = 0

    for all_tokens, mask in val_sequences:
        input_ids = all_tokens[:-1]
        target_ids = all_tokens[1:]
        logits = model.forward(input_ids)
        probs = softmax_np(logits, axis=-1)
        target_probs = probs[np.arange(len(target_ids)), target_ids]
        unweighted_loss = -np.log(np.maximum(target_probs, 1e-12))
        masked_loss = np.sum(unweighted_loss * mask)
        n_target = np.sum(mask)
        total_val_loss += masked_loss
        total_val_tokens += int(n_target)

    avg_loss = total_val_loss / max(1, total_val_tokens)
    perplexity = math.exp(min(avg_loss, 20.0))
    return avg_loss, perplexity


def train_capacity_model(
    config: NairaModelConfig,
    tokenizer: NairaTokenizer,
    experiment_name: str,
    save_filename: str,
    num_epochs: int = 20,
    learning_rate: float = 4e-3,
) -> tuple[NumpyNairaModel, dict[str, Any]]:
    """Train a capacity-scaled NairaLLM model with exact parity."""
    dm = DatasetManager()
    dataset_file = dm.reviewed_dir / "v1_1_expanded_dataset.jsonl"
    all_samples = dm.load_jsonl(dataset_file)
    train_samples, val_samples, test_samples = dm.split_dataset(
        all_samples,
        train_ratio=0.8,
        val_ratio=0.1,
        test_ratio=0.1,
        seed=42,
    )

    train_sequences = format_dataset_with_instruction_mask(train_samples, tokenizer, config.max_seq_len)
    val_sequences = format_dataset_with_instruction_mask(val_samples, tokenizer, config.max_seq_len)

    # Compute parameters
    param_count = config.vocab_size * config.d_model * 2 + config.d_model  # emb + out + norm
    for _ in range(config.num_layers):
        param_count += config.d_model * 2 + 4 * (config.d_model**2) + 3 * (config.d_model * config.d_ff)
    mem_mb = param_count * 4 / (1024 * 1024)

    print(f"\n========================================================")
    print(f" TRAINING: {experiment_name.upper()}")
    print(f" Parameters: {param_count:,} ({mem_mb:.2f} MB float32)")
    print(f" Architecture: d_model={config.d_model}, layers={config.num_layers}, heads={config.num_heads}, d_ff={config.d_ff}, max_seq_len={config.max_seq_len}")
    print(f" Dataset: {len(train_sequences)} Train / {len(val_sequences)} Val Sequences")
    print(f" Optimization: Adam (lr={learning_rate}, cosine schedule, {num_epochs} epochs)")
    print(f"========================================================")

    model = NumpyNairaModel(config)
    weights = model.weights

    # Initialize Adam states
    m = {k: np.zeros_like(v) for k, v in weights.items()}
    v = {k: np.zeros_like(v) for k, v in weights.items()}
    beta1, beta2, eps = 0.9, 0.999, 1e-8
    step = 0
    scale = 1.0 / math.sqrt(config.d_head)

    # Pre-allocate causal mask cache up to max_seq_len
    max_len = config.max_seq_len
    full_causal_mask = np.triu(np.full((max_len, max_len), -1e9, dtype=np.float32), k=1)

    epoch_logs: list[dict[str, Any]] = []
    t_start = time.perf_counter()

    for epoch in range(num_epochs):
        t_ep_start = time.perf_counter()
        epoch_loss = 0.0
        n_tokens = 0
        indices = list(range(len(train_sequences)))
        # Fixed deterministic per-epoch shuffle
        rng = np.random.RandomState(42 + epoch)
        rng.shuffle(indices)

        # Cosine learning rate schedule
        curr_lr = learning_rate * 0.5 * (1.0 + math.cos(math.pi * epoch / num_epochs))

        for seq_idx in indices:
            all_tokens, mask = train_sequences[seq_idx]
            input_ids = all_tokens[:-1]
            target_ids = all_tokens[1:]
            seq_len = len(input_ids)
            causal_mask = full_causal_mask[:seq_len, :seq_len]

            # Forward pass
            h = weights["tok_embeddings"][input_ids]
            layer_acts = []

            for i in range(config.num_layers):
                norm_h = rms_norm(h, weights[f"layer_{i}_attn_norm"], config.norm_eps)
                q = (norm_h @ weights[f"layer_{i}_q_proj"]).reshape(seq_len, config.num_heads, config.d_head)
                k = (norm_h @ weights[f"layer_{i}_k_proj"]).reshape(seq_len, config.num_kv_heads, config.d_head)
                val = (norm_h @ weights[f"layer_{i}_v_proj"]).reshape(seq_len, config.num_kv_heads, config.d_head)

                q_rope = apply_rope_np(q, model.cos, model.sin)
                k_rope = apply_rope_np(k, model.cos, model.sin)

                q_t = np.transpose(q_rope, (1, 0, 2))
                k_t = np.transpose(k_rope, (1, 0, 2))
                v_t = np.transpose(val, (1, 0, 2))

                scores = (q_t @ np.transpose(k_t, (0, 2, 1))) * scale + causal_mask
                exp_scores = np.exp(scores - np.max(scores, axis=-1, keepdims=True))
                attn_w = exp_scores / np.sum(exp_scores, axis=-1, keepdims=True)

                attn_out = attn_w @ v_t
                attn_out_flat = np.transpose(attn_out, (1, 0, 2)).reshape(seq_len, config.d_model)
                h_post_attn = h + (attn_out_flat @ weights[f"layer_{i}_out_proj"])

                norm_ffn = rms_norm(h_post_attn, weights[f"layer_{i}_ffn_norm"], config.norm_eps)
                w1_out = norm_ffn @ weights[f"layer_{i}_w1"]
                w3_out = norm_ffn @ weights[f"layer_{i}_w3"]
                silu_w1 = silu(w1_out)
                swiglu_out = (silu_w1 * w3_out) @ weights[f"layer_{i}_w2"]
                h_post_ffn = h_post_attn + swiglu_out

                layer_acts.append(
                    {
                        "h_in": h,
                        "norm_h": norm_h,
                        "attn_w": attn_w,
                        "v_t": v_t,
                        "q_t": q_t,
                        "k_t": k_t,
                        "attn_out_flat": attn_out_flat,
                        "h_post_attn": h_post_attn,
                        "norm_ffn": norm_ffn,
                        "w1_out": w1_out,
                        "w3_out": w3_out,
                        "silu_w1": silu_w1,
                    }
                )
                h = h_post_ffn

            final_norm = rms_norm(h, weights["norm_weight"], config.norm_eps)
            logits = final_norm @ weights["output_weight"]

            probs = softmax_np(logits, axis=-1)
            target_probs = probs[np.arange(len(target_ids)), target_ids]

            # Instruction-masked cross-entropy loss
            unweighted_loss = -np.log(np.maximum(target_probs, 1e-12))
            masked_loss = np.sum(unweighted_loss * mask)
            n_target = max(1.0, np.sum(mask))
            epoch_loss += masked_loss
            n_tokens += int(n_target)

            # Masked backpropagation
            dlogits = probs.copy()
            dlogits[np.arange(len(target_ids)), target_ids] -= 1.0
            dlogits = dlogits * mask[:, None]

            grads: dict[str, np.ndarray] = {}
            grads["output_weight"] = final_norm.T @ dlogits
            dh = dlogits @ weights["output_weight"].T

            for i in reversed(range(config.num_layers)):
                act = layer_acts[i]
                # FFN backpropagation
                d_w2 = (act["silu_w1"] * act["w3_out"]).T @ dh
                grads[f"layer_{i}_w2"] = d_w2
                d_swiglu = dh @ weights[f"layer_{i}_w2"].T

                d_silu_w1 = d_swiglu * act["w3_out"]
                d_w3_out = d_swiglu * act["silu_w1"]

                grads[f"layer_{i}_w3"] = act["norm_ffn"].T @ d_w3_out
                grads[f"layer_{i}_w1"] = act["norm_ffn"].T @ (d_silu_w1 * d_silu(act["w1_out"]))

                # Attn out_proj backpropagation
                grads[f"layer_{i}_out_proj"] = act["attn_out_flat"].T @ dh
                d_attn_out_flat = dh @ weights[f"layer_{i}_out_proj"].T
                d_attn_out = np.transpose(d_attn_out_flat.reshape(seq_len, config.num_heads, config.d_head), (1, 0, 2))

                # Gradient w.r.t v_t
                d_v_t = np.transpose(act["attn_w"], (0, 2, 1)) @ d_attn_out
                d_v_flat = np.transpose(d_v_t, (1, 0, 2)).reshape(seq_len, config.d_model)
                grads[f"layer_{i}_v_proj"] = act["norm_h"].T @ d_v_flat

                # Gradient w.r.t attention scores
                d_attn_w = d_attn_out @ np.transpose(act["v_t"], (0, 2, 1))
                sum_d = np.sum(d_attn_w * act["attn_w"], axis=-1, keepdims=True)
                d_scores = act["attn_w"] * (d_attn_w - sum_d) * scale

                # Gradient w.r.t q_t and k_t
                d_q_t = d_scores @ act["k_t"]
                d_k_t = np.transpose(d_scores, (0, 2, 1)) @ act["q_t"]

                d_q_flat = np.transpose(d_q_t, (1, 0, 2)).reshape(seq_len, config.d_model)
                d_k_flat = np.transpose(d_k_t, (1, 0, 2)).reshape(seq_len, config.d_model)

                grads[f"layer_{i}_q_proj"] = act["norm_h"].T @ d_q_flat
                grads[f"layer_{i}_k_proj"] = act["norm_h"].T @ d_k_flat

            # Embedding gradients
            d_tok_emb_matrix = np.zeros_like(weights["tok_embeddings"])
            np.add.at(d_tok_emb_matrix, input_ids, dh)
            grads["tok_embeddings"] = d_tok_emb_matrix

            # Adam update
            step += 1
            for name, grad in grads.items():
                if name in weights:
                    np.clip(grad, -1.0, 1.0, out=grad)
                    m[name] = beta1 * m[name] + (1 - beta1) * grad
                    v[name] = beta2 * v[name] + (1 - beta2) * (grad**2)
                    m_hat = m[name] / (1 - beta1**step)
                    v_hat = v[name] / (1 - beta2**step)
                    weights[name] -= curr_lr * m_hat / (np.sqrt(v_hat) + eps)

        avg_train_loss = epoch_loss / max(1, n_tokens)
        val_loss, val_ppl = evaluate_masked_val_loss(model, val_sequences)
        train_ppl = math.exp(min(avg_train_loss, 20.0))
        t_ep_elapsed = time.perf_counter() - t_ep_start

        log_item = {
            "epoch": epoch + 1,
            "train_loss": round(float(avg_train_loss), 4),
            "train_perplexity": round(float(train_ppl), 2),
            "val_loss": round(float(val_loss), 4),
            "val_perplexity": round(float(val_ppl), 2),
            "lr": round(float(curr_lr), 6),
            "epoch_time_seconds": round(float(t_ep_elapsed), 2),
        }
        epoch_logs.append(log_item)

        # Save intermediate checkpoint after each epoch
        save_path = Path("NairaLLM/training/checkpoints") / save_filename
        save_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(str(save_path), **weights)

        print(
            f"Epoch {epoch + 1:02d}/{num_epochs:02d} — Train Loss: {avg_train_loss:.4f} (PPL: {train_ppl:.2f}) | Val Loss: {val_loss:.4f} (PPL: {val_ppl:.2f}) | LR: {curr_lr:.5f} ({t_ep_elapsed:.1f}s)",
            flush=True,
        )

    elapsed_total = time.perf_counter() - t_start

    ckpt_metadata = {
        "experiment_name": experiment_name,
        "model_config": config.to_dict(),
        "parameters": param_count,
        "memory_mb": round(mem_mb, 2),
        "tokenizer_version": "1.0 (Byte-Level BPE, 1507 tokens)",
        "dataset_version": "v1.2 (561 reviewed samples)",
        "num_epochs": num_epochs,
        "final_train_loss": float(epoch_logs[-1]["train_loss"]),
        "final_train_perplexity": float(epoch_logs[-1]["train_perplexity"]),
        "final_val_loss": float(epoch_logs[-1]["val_loss"]),
        "final_val_perplexity": float(epoch_logs[-1]["val_perplexity"]),
        "training_time_seconds": round(float(elapsed_total), 2),
        "history": epoch_logs,
    }

    # Save checkpoint and metadata
    save_path = Path("NairaLLM/training/checkpoints") / save_filename
    save_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(str(save_path), **weights)
    print(f"\n[SAVED] Checkpoint weights saved to {save_path}")

    meta_path = save_path.parent / f"{save_path.stem}_metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(ckpt_metadata, f, indent=2)
    print(f"[SAVED] Checkpoint metadata saved to {meta_path}")

    return model, ckpt_metadata


def main() -> None:
    tokenizer_path = Path("NairaLLM/model/tokenizer/naira_tokenizer.json")
    tokenizer = NairaTokenizer(tokenizer_path)

    # 1. Train Experiment B: Small Scale (128-dim, 4 layers, 4 heads, d_ff=512)
    small_ckpt = Path("NairaLLM/training/checkpoints/numpy_model_v1_3_small.npz")
    if not small_ckpt.exists():
        config_b = NairaModelConfig(
            vocab_size=tokenizer.vocab_size,
            d_model=128,
            num_layers=4,
            num_heads=4,
            num_kv_heads=4,
            d_ff=512,
            max_seq_len=256,
        )
        print("==================================================================")
        print("      STARTING EXPERIMENT B: V1.3 SMALL SCALE CAPACITY RUN        ")
        print("==================================================================")
        train_capacity_model(
            config=config_b,
            tokenizer=tokenizer,
            experiment_name="NairaLLM V1.3 Small Scale",
            save_filename="numpy_model_v1_3_small.npz",
            num_epochs=20,
            learning_rate=4e-3,
        )
    else:
        print(f"[SKIP] Experiment B checkpoint already exists at {small_ckpt}")

    # 2. Train Experiment C: Medium Scale (256-dim, 6 layers, 8 heads, d_ff=1024)
    config_c = NairaModelConfig(
        vocab_size=tokenizer.vocab_size,
        d_model=256,
        num_layers=6,
        num_heads=8,
        num_kv_heads=8,
        d_ff=1024,
        max_seq_len=256,
    )
    print("==================================================================")
    print("      STARTING EXPERIMENT C: V1.3 MEDIUM SCALE CAPACITY RUN       ")
    print("==================================================================")
    train_capacity_model(
        config=config_c,
        tokenizer=tokenizer,
        experiment_name="NairaLLM V1.3 Medium Scale",
        save_filename="numpy_model_v1_3_medium.npz",
        num_epochs=6,
        learning_rate=3e-3,
    )


if __name__ == "__main__":
    main()
