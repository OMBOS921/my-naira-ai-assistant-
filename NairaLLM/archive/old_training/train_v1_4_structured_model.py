"""
NairaLLM V1.4 Structured Cognition / Intent-Conditioned Training Pipeline.

Trains the lightweight Naira Transformer on structured cognition examples:
Natural Language -> <|intent|> -> <|tool_call|> / <|plan|> / <|final|>

Features:
- Pure NumPy CPU execution
- Target-Only Instruction Masking
- Multilingual Curriculum (English, Hindi, Hinglish)
- Contrastive Safe/Destructive & Read/Write Sets
- Adam Optimizer + Cosine Schedule
- Saves active runtime checkpoint numpy_model.npz & numpy_model_v1_4.npz
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
from NairaLLM.dataset.schemas.dataset_schema import NairaDatasetSample
from NairaLLM.model.config.model_config import NairaModelConfig
from NairaLLM.model.runtime.numpy_backend import (
    NumpyNairaModel,
    apply_rope_np,
    rms_norm,
)
from NairaLLM.model.tokenizer.naira_tokenizer import NairaTokenizer

_LOG = logging.getLogger("nairallm.train_v1_4")


def softmax_np(x: np.ndarray, axis: int = -1) -> np.ndarray:
    e_x = np.exp(x - np.max(x, axis=axis, keepdims=True))
    return e_x / np.sum(e_x, axis=axis, keepdims=True)


def silu(x: np.ndarray) -> np.ndarray:
    return x / (1.0 + np.exp(-np.clip(x, -30.0, 30.0)))


def d_silu(x: np.ndarray) -> np.ndarray:
    s = 1.0 / (1.0 + np.exp(-np.clip(x, -30.0, 30.0)))
    return s * (1.0 + x * (1.0 - s))


def format_dataset_with_instruction_mask(
    samples: list[NairaDatasetSample],
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
    config: NairaModelConfig,
) -> float:
    total_loss = 0.0
    total_tokens = 0
    cos, sin = model.cos, model.sin

    for all_tokens, mask in val_sequences:
        seq_len = len(all_tokens)
        if seq_len < 2:
            continue

        input_ids = all_tokens[:-1]
        targets = all_tokens[1:]
        T = len(input_ids)

        x = model.weights["tok_embeddings"][input_ids]

        for i in range(config.num_layers):
            norm_attn = rms_norm(x, model.weights[f"layer_{i}_attn_norm"])
            q = norm_attn @ model.weights[f"layer_{i}_q_proj"]
            k = norm_attn @ model.weights[f"layer_{i}_k_proj"]
            v = norm_attn @ model.weights[f"layer_{i}_v_proj"]

            q = q.reshape(T, config.num_heads, config.d_head)
            k = k.reshape(T, config.num_kv_heads, config.d_head)
            v = v.reshape(T, config.num_kv_heads, config.d_head)

            q = apply_rope_np(q, cos, sin)
            k = apply_rope_np(k, cos, sin)

            q_t = q.transpose(1, 0, 2)
            k_t = k.transpose(1, 0, 2)
            v_t = v.transpose(1, 0, 2)

            scores = (q_t @ k_t.transpose(0, 2, 1)) / math.sqrt(config.d_head)
            causal_mask = np.triu(np.ones((T, T), dtype=bool), k=1)
            scores[:, causal_mask] = -1e9
            attn_weights = softmax_np(scores, axis=-1)
            attn_out = (attn_weights @ v_t).transpose(1, 0, 2).reshape(T, config.d_model)
            attn_proj = attn_out @ model.weights[f"layer_{i}_out_proj"]
            x = x + attn_proj

            norm_ffn = rms_norm(x, model.weights[f"layer_{i}_ffn_norm"])
            x_w1 = norm_ffn @ model.weights[f"layer_{i}_w1"]
            s_w1 = silu(x_w1)
            x_w3 = norm_ffn @ model.weights[f"layer_{i}_w3"]
            ffn_out = (s_w1 * x_w3) @ model.weights[f"layer_{i}_w2"]
            x = x + ffn_out

        norm_final = rms_norm(x, model.weights["norm_weight"])
        logits = norm_final @ model.weights["output_weight"]
        probs = softmax_np(logits, axis=-1)

        loss_t = -np.log(np.clip(probs[np.arange(T), targets], 1e-12, 1.0))
        masked_loss = np.sum(loss_t * mask)
        num_tgt = np.sum(mask)

        if num_tgt > 0:
            total_loss += masked_loss
            total_tokens += int(num_tgt)

    return total_loss / max(1, total_tokens)


def train_v1_4_structured_model(
    epochs: int = 25,
    learning_rate: float = 0.008,
    d_model: int = 64,
    num_layers: int = 2,
    num_heads: int = 2,
    d_ff: int = 128,
) -> dict[str, Any]:
    print("==================================================")
    print("  NAIRALLM V1.4 — STRUCTURED COGNITION TRAINING   ")
    print("==================================================")

    # 1. Load Dataset
    dm = DatasetManager()
    v1_4_file = dm.reviewed_dir / "v1_4_structured_dataset.jsonl"
    if not v1_4_file.exists():
        from NairaLLM.dataset.build_v1_4_structured_dataset import main as build_ds
        build_ds()

    samples = dm.load_jsonl(v1_4_file)
    print(f"Loaded {len(samples)} structured cognition samples from {v1_4_file.name}")

    # 2. Tokenizer
    tok_path = Path("NairaLLM/model/tokenizer/naira_tokenizer.json")
    tokenizer = NairaTokenizer(tok_path)
    vocab_size = tokenizer.vocab_size
    print(f"Loaded NairaTokenizer (vocab_size={vocab_size})")

    # 3. Deterministic 80/10/10 split
    rng = np.random.RandomState(42)
    indices = np.arange(len(samples))
    rng.shuffle(indices)

    n_train = int(len(samples) * 0.8)
    n_val = int(len(samples) * 0.1)

    train_samples = [samples[i] for i in indices[:n_train]]
    val_samples = [samples[i] for i in indices[n_train : n_train + n_val]]
    test_samples = [samples[i] for i in indices[n_train + n_val :]]

    train_seqs = format_dataset_with_instruction_mask(train_samples, tokenizer)
    val_seqs = format_dataset_with_instruction_mask(val_samples, tokenizer)

    print(f"Dataset Split: Train={len(train_seqs)}, Val={len(val_seqs)}, Test={len(test_samples)}")

    # 4. Initialize Small Model Configuration
    config = NairaModelConfig(
        vocab_size=vocab_size,
        d_model=d_model,
        num_layers=num_layers,
        num_heads=num_heads,
        num_kv_heads=num_heads,
        d_ff=d_ff,
        max_seq_len=256,
    )
    model = NumpyNairaModel(config)
    cos, sin = model.cos, model.sin

    # Count parameters
    total_params = (
        config.vocab_size * config.d_model
        + config.d_model
        + config.d_model * config.vocab_size
        + config.num_layers
        * (
            config.d_model * 2
            + config.d_model * config.d_model * 4
            + config.d_model * config.d_ff * 3
        )
    )
    print(f"Model Architecture: d_model={config.d_model}, layers={config.num_layers}, heads={config.num_heads}, d_ff={config.d_ff}")
    print(f"Total Parameters: {total_params:,}")

    # 5. Adam Optimizer & LR Schedule
    m_dict = {k: np.zeros_like(v) for k, v in model.weights.items()}
    v_dict = {k: np.zeros_like(v) for k, v in model.weights.items()}
    beta1, beta2, eps = 0.9, 0.999, 1e-8
    global_step = 0
    total_steps = epochs * len(train_seqs)

    history = {
        "train_loss": [],
        "val_loss": [],
        "epochs": [],
        "epoch_times": [],
    }

    print("\nBeginning Training Loop...")
    start_time = time.perf_counter()

    for epoch in range(1, epochs + 1):
        ep_start = time.perf_counter()
        total_loss = 0.0
        total_tokens = 0

        # Shuffle training sequences each epoch
        perm = rng.permutation(len(train_seqs))

        for idx in perm:
            all_tokens, mask = train_seqs[idx]
            seq_len = len(all_tokens)
            if seq_len < 2:
                continue

            input_ids = all_tokens[:-1]
            targets = all_tokens[1:]
            T = len(input_ids)

            # Forward pass
            x = model.weights["tok_embeddings"][input_ids]
            layer_cache = []

            for i in range(config.num_layers):
                norm_attn = rms_norm(x, model.weights[f"layer_{i}_attn_norm"])
                q = norm_attn @ model.weights[f"layer_{i}_q_proj"]
                k = norm_attn @ model.weights[f"layer_{i}_k_proj"]
                v = norm_attn @ model.weights[f"layer_{i}_v_proj"]

                q = q.reshape(T, config.num_heads, config.d_head)
                k = k.reshape(T, config.num_kv_heads, config.d_head)
                v = v.reshape(T, config.num_kv_heads, config.d_head)

                q = apply_rope_np(q, cos, sin)
                k = apply_rope_np(k, cos, sin)

                q_t = q.transpose(1, 0, 2)
                k_t = k.transpose(1, 0, 2)
                v_t = v.transpose(1, 0, 2)

                scores = (q_t @ k_t.transpose(0, 2, 1)) / math.sqrt(config.d_head)
                causal_mask = np.triu(np.ones((T, T), dtype=bool), k=1)
                scores[:, causal_mask] = -1e9
                attn_weights = softmax_np(scores, axis=-1)
                attn_out = (attn_weights @ v_t).transpose(1, 0, 2).reshape(T, config.d_model)
                attn_proj = attn_out @ model.weights[f"layer_{i}_out_proj"]
                x = x + attn_proj

                norm_ffn = rms_norm(x, model.weights[f"layer_{i}_ffn_norm"])
                x_w1 = norm_ffn @ model.weights[f"layer_{i}_w1"]
                s_w1 = silu(x_w1)
                x_w3 = norm_ffn @ model.weights[f"layer_{i}_w3"]
                ffn_out = (s_w1 * x_w3) @ model.weights[f"layer_{i}_w2"]
                x = x + ffn_out

                layer_cache.append((norm_attn, q, k, v, attn_weights, attn_out, norm_ffn, x_w1, s_w1, x_w3))

            norm_final = rms_norm(x, model.weights["norm_weight"])
            logits = norm_final @ model.weights["output_weight"]
            probs = softmax_np(logits, axis=-1)

            # Masked Cross-Entropy Loss
            loss_t = -np.log(np.clip(probs[np.arange(T), targets], 1e-12, 1.0))
            masked_loss = np.sum(loss_t * mask)
            num_tgt = np.sum(mask)

            if num_tgt > 0:
                total_loss += masked_loss
                total_tokens += int(num_tgt)

                # Backward pass
                dlogits = probs.copy()
                dlogits[np.arange(T), targets] -= 1.0
                dlogits = dlogits * mask[:, None]

                grads = {}
                grads["output_weight"] = norm_final.T @ dlogits
                dx = dlogits @ model.weights["output_weight"].T
                grads["norm_weight"] = np.sum(dx * norm_final, axis=0)

                for i in reversed(range(config.num_layers)):
                    norm_attn, q, k, v, attn_weights, attn_out, norm_ffn, x_w1, s_w1, x_w3 = layer_cache[i]

                    # FFN
                    d_w2 = (s_w1 * x_w3).T @ dx
                    grads[f"layer_{i}_w2"] = d_w2
                    d_swiglu = dx @ model.weights[f"layer_{i}_w2"].T
                    d_s_w1 = d_swiglu * x_w3
                    d_x_w3 = d_swiglu * s_w1
                    d_x_w1 = d_s_w1 * d_silu(x_w1)
                    grads[f"layer_{i}_w1"] = norm_ffn.T @ d_x_w1
                    grads[f"layer_{i}_w3"] = norm_ffn.T @ d_x_w3
                    d_norm_ffn = d_x_w1 @ model.weights[f"layer_{i}_w1"].T + d_x_w3 @ model.weights[f"layer_{i}_w3"].T
                    grads[f"layer_{i}_ffn_norm"] = np.sum(d_norm_ffn * norm_ffn, axis=0)
                    dx = dx + d_norm_ffn

                    # Attention
                    grads[f"layer_{i}_out_proj"] = attn_out.T @ dx
                    d_attn_out_flat = dx @ model.weights[f"layer_{i}_out_proj"].T
                    d_attn_out = np.transpose(d_attn_out_flat.reshape(T, config.num_heads, config.d_head), (1, 0, 2))

                    d_v_t = np.transpose(attn_weights, (0, 2, 1)) @ d_attn_out
                    d_v_flat = np.transpose(d_v_t, (1, 0, 2)).reshape(T, config.d_model)
                    grads[f"layer_{i}_v_proj"] = norm_attn.T @ d_v_flat

                    d_attn_w = d_attn_out @ np.transpose(v_t, (0, 2, 1))
                    sum_d = np.sum(d_attn_w * attn_weights, axis=-1, keepdims=True)
                    scale = 1.0 / math.sqrt(config.d_head)
                    d_scores = attn_weights * (d_attn_w - sum_d) * scale

                    d_q_t = d_scores @ k_t
                    d_k_t = np.transpose(d_scores, (0, 2, 1)) @ q_t

                    d_q_flat = np.transpose(d_q_t, (1, 0, 2)).reshape(T, config.d_model)
                    d_k_flat = np.transpose(d_k_t, (1, 0, 2)).reshape(T, config.d_model)

                    grads[f"layer_{i}_q_proj"] = norm_attn.T @ d_q_flat
                    grads[f"layer_{i}_k_proj"] = norm_attn.T @ d_k_flat

                    d_norm_attn = (
                        d_v_flat @ model.weights[f"layer_{i}_v_proj"].T
                        + d_q_flat @ model.weights[f"layer_{i}_q_proj"].T
                        + d_k_flat @ model.weights[f"layer_{i}_k_proj"].T
                    )
                    grads[f"layer_{i}_attn_norm"] = np.sum(d_norm_attn * norm_attn, axis=0)
                    dx = dx + d_norm_attn

                # Embedding gradient
                d_tok_emb_matrix = np.zeros_like(model.weights["tok_embeddings"])
                np.add.at(d_tok_emb_matrix, input_ids, dx)
                grads["tok_embeddings"] = d_tok_emb_matrix

                # Optimizer step with Cosine Annealing
                global_step += 1
                progress = min(1.0, global_step / max(1, total_steps))
                current_lr = 0.0005 + 0.5 * (learning_rate - 0.0005) * (1.0 + math.cos(math.pi * progress))

                for param_name in model.weights:
                    if param_name in grads:
                        g = grads[param_name]
                        g = np.clip(g, -1.0, 1.0)
                        m_dict[param_name] = beta1 * m_dict[param_name] + (1.0 - beta1) * g
                        v_dict[param_name] = beta2 * v_dict[param_name] + (1.0 - beta2) * (g ** 2)
                        m_hat = m_dict[param_name] / (1.0 - beta1 ** global_step)
                        v_hat = v_dict[param_name] / (1.0 - beta2 ** global_step)
                        model.weights[param_name] -= current_lr * m_hat / (np.sqrt(v_hat) + eps)

        train_loss = total_loss / max(1, total_tokens)
        val_loss = evaluate_masked_val_loss(model, val_seqs, config)
        ep_dt = time.perf_counter() - ep_start

        history["epochs"].append(epoch)
        history["train_loss"].append(round(float(train_loss), 4))
        history["val_loss"].append(round(float(val_loss), 4))
        history["epoch_times"].append(round(ep_dt, 2))

        print(f"Epoch {epoch:2d}/{epochs} | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | Time: {ep_dt:.2f}s")

    total_training_time = time.perf_counter() - start_time
    print(f"\nTraining completed in {total_training_time:.2f}s ({total_training_time/60:.2f} min)")

    # 6. Save Checkpoint
    ckpt_dir = Path("NairaLLM/training/checkpoints")
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    v1_4_ckpt = ckpt_dir / "numpy_model_v1_4.npz"
    active_ckpt = ckpt_dir / "numpy_model.npz"

    np.savez_compressed(str(v1_4_ckpt), **model.weights)
    np.savez_compressed(str(active_ckpt), **model.weights)

    metadata = {
        "version": "1.4",
        "description": "NairaLLM V1.4 Structured Cognition / Intent-Conditioned Model",
        "model_config": config.to_dict(),
        "total_parameters": total_params,
        "epochs": epochs,
        "final_train_loss": history["train_loss"][-1],
        "final_val_loss": history["val_loss"][-1],
        "training_time_seconds": round(total_training_time, 2),
        "history": history,
    }

    meta_file = ckpt_dir / "numpy_model_v1_4_metadata.json"
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    active_meta_file = ckpt_dir / "numpy_model_metadata.json"
    with open(active_meta_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"Saved checkpoints to:")
    print(f"  - {v1_4_ckpt}")
    print(f"  - {active_ckpt}")
    print(f"  - {meta_file}")

    return metadata


if __name__ == "__main__":
    train_v1_4_structured_model(epochs=30, learning_rate=0.012)
