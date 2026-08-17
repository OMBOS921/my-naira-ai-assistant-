"""
NairaLLM V1.2 Full Neural Training Pipeline with Supervised Instruction Masking.

Trains the 64-dim 2-layer Causal Transformer with:
1. Target-Only Instruction Masking (Prompt tokens masked to 0.0, Assistant responses trained at 1.0)
2. Full Analytical Neural Backpropagation across Attention Q/K/V/Out projections, SwiGLU FFN, RMSNorm, Output Head, and Embeddings
3. Adam Optimizer with Cosine Learning Rate Schedule
4. Validation Loss and Perplexity Evaluation on Held-Out Split
5. Exports V1.2 Checkpoint and Training Metadata
"""

from __future__ import annotations

import json
import logging
import math
import sys
import time
from pathlib import Path
from typing import Any
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from NairaLLM.dataset.dataset_manager import DatasetManager
from NairaLLM.model.config.model_config import NairaModelConfig
from NairaLLM.model.runtime.numpy_backend import (
    NumpyNairaModel,
    apply_rope_np,
    rms_norm,
    swiglu,
)
from NairaLLM.model.tokenizer.naira_tokenizer import NairaTokenizer

_LOG = logging.getLogger("nairallm.train_v1_2")


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


def evaluate_masked_val_loss(model: NumpyNairaModel, val_sequences: list[tuple[list[int], np.ndarray]]) -> tuple[float, float]:
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


def train_v1_2_model(
    config: NairaModelConfig,
    tokenizer: NairaTokenizer,
    num_epochs: int = 20,
    learning_rate: float = 4e-3,
    save_path: str | Path | None = None,
) -> tuple[NumpyNairaModel, dict[str, Any]]:
    dm = DatasetManager()
    all_samples = dm.load_jsonl(dm.reviewed_dir / "v1_1_expanded_dataset.jsonl")
    train_samples, val_samples, test_samples = dm.split_dataset(all_samples, train_ratio=0.8, val_ratio=0.1, test_ratio=0.1)

    train_sequences = format_dataset_with_instruction_mask(train_samples, tokenizer, config.max_seq_len)
    val_sequences = format_dataset_with_instruction_mask(val_samples, tokenizer, config.max_seq_len)

    print(f"Loaded {len(train_sequences)} masked train sequences and {len(val_sequences)} validation sequences.")
    print(f"Model Architecture: d_model={config.d_model}, layers={config.num_layers}, heads={config.num_heads}, d_ff={config.d_ff}, vocab={config.vocab_size}")

    model = NumpyNairaModel(config)
    weights = model.weights

    # Initialize Adam optimizer states for all weights
    m = {k: np.zeros_like(v) for k, v in weights.items()}
    v = {k: np.zeros_like(v) for k, v in weights.items()}
    beta1, beta2, eps = 0.9, 0.999, 1e-8
    step = 0

    scale = 1.0 / math.sqrt(config.d_head)
    print(f"Starting NairaLLM V1.2 Neural Instruction-Masked Training ({num_epochs} epochs)...")

    epoch_logs: list[dict[str, Any]] = []
    t_start = time.perf_counter()

    for epoch in range(num_epochs):
        epoch_loss = 0.0
        n_tokens = 0
        indices = list(range(len(train_sequences)))
        np.random.shuffle(indices)

        # Cosine learning rate schedule
        curr_lr = learning_rate * 0.5 * (1.0 + math.cos(math.pi * epoch / num_epochs))

        for seq_idx in indices:
            all_tokens, mask = train_sequences[seq_idx]
            input_ids = all_tokens[:-1]
            target_ids = all_tokens[1:]
            seq_len = len(input_ids)

            # Forward pass with layer activation caching
            h0 = weights["tok_embeddings"][input_ids]
            causal_mask = np.triu(np.full((seq_len, seq_len), -1e9, dtype=np.float32), k=1)

            layer_acts = []
            h = h0

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

            step += 1
            for name, grad in grads.items():
                if name in weights:
                    np.clip(grad, -1.0, 1.0, out=grad)
                    m[name] = beta1 * m[name] + (1 - beta1) * grad
                    v[name] = beta2 * v[name] + (1 - beta2) * (grad ** 2)
                    m_hat = m[name] / (1 - beta1 ** step)
                    v_hat = v[name] / (1 - beta2 ** step)
                    weights[name] -= curr_lr * m_hat / (np.sqrt(v_hat) + eps)

        avg_train_loss = epoch_loss / max(1, n_tokens)
        val_loss, val_ppl = evaluate_masked_val_loss(model, val_sequences)
        train_ppl = math.exp(min(avg_train_loss, 20.0))

        log_item = {
            "epoch": epoch + 1,
            "train_loss": round(float(avg_train_loss), 4),
            "train_perplexity": round(float(train_ppl), 2),
            "val_loss": round(float(val_loss), 4),
            "val_perplexity": round(float(val_ppl), 2),
            "lr": round(float(curr_lr), 6),
        }
        epoch_logs.append(log_item)

        print(
            f"Epoch {epoch + 1:02d}/{num_epochs:02d} — Train Loss: {avg_train_loss:.4f} (PPL: {train_ppl:.2f}) | Val Loss: {val_loss:.4f} (PPL: {val_ppl:.2f}) | LR: {curr_lr:.5f}",
            flush=True,
        )

    elapsed = time.perf_counter() - t_start

    ckpt_metadata = {
        "dataset_version": "v1.2",
        "model_config": config.to_dict(),
        "tokenizer_version": "1.0 (Byte-Level BPE)",
        "num_epochs": num_epochs,
        "final_train_loss": float(epoch_logs[-1]["train_loss"]),
        "final_val_loss": float(epoch_logs[-1]["val_loss"]),
        "final_perplexity": float(epoch_logs[-1]["val_perplexity"]),
        "training_time_seconds": round(float(elapsed), 2),
        "history": epoch_logs,
    }

    if save_path:
        path = Path(save_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(str(path), **weights)
        print(f"Saved NairaLLM V1.2 weights to {path}", flush=True)

        meta_path = path.parent / f"{path.stem}_metadata.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(ckpt_metadata, f, indent=2, default=float)
        print(f"Saved training metadata to {meta_path}", flush=True)

        default_model_path = path.parent / "numpy_model.npz"
        np.savez_compressed(str(default_model_path), **weights)
        print(f"Updated default active checkpoint at {default_model_path}", flush=True)

    return model, ckpt_metadata


def main() -> None:
    tokenizer_path = Path("NairaLLM/model/tokenizer/naira_tokenizer.json")
    tokenizer = NairaTokenizer(tokenizer_path)

    config = NairaModelConfig(
        vocab_size=tokenizer.vocab_size,
        d_model=64,
        num_layers=2,
        num_heads=2,
        num_kv_heads=2,
        d_ff=128,
        max_seq_len=256,
    )

    save_file = Path("NairaLLM/training/checkpoints/numpy_model_v1_2.npz")
    train_v1_2_model(config, tokenizer, num_epochs=20, learning_rate=4e-3, save_path=save_file)


if __name__ == "__main__":
    main()
