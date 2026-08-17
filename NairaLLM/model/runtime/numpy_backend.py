"""
Lightweight Pure-NumPy Inference and Execution Backend for NairaLLM.

Provides a fast, zero-external-dependency execution path for NairaLLM on CPU.
Supports:
- RMSNorm
- Rotary Position Embeddings (RoPE)
- SwiGLU activations
- Causal Multi-Head Attention
- Autoregressive greedy/sampling generation
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any
import numpy as np

from NairaLLM.model.config.model_config import NairaModelConfig
from NairaLLM.model.tokenizer.naira_tokenizer import NairaTokenizer


def rms_norm(x: np.ndarray, weight: np.ndarray, eps: float = 1e-5) -> np.ndarray:
    norm = 1.0 / np.sqrt(np.mean(x ** 2, axis=-1, keepdims=True) + eps)
    return x * norm * weight


def swiglu(x: np.ndarray, w1: np.ndarray, w2: np.ndarray, w3: np.ndarray) -> np.ndarray:
    # silu(x * w1) * (x * w3) @ w2
    x_w1 = x @ w1
    silu_w1 = x_w1 / (1.0 + np.exp(-np.clip(x_w1, -30.0, 30.0)))
    x_w3 = x @ w3
    return (silu_w1 * x_w3) @ w2


def precompute_rope_freqs_np(dim: int, max_seq_len: int, theta: float = 10000.0) -> np.ndarray:
    freqs = 1.0 / (theta ** (np.arange(0, dim, 2)[: (dim // 2)].astype(np.float32) / dim))
    t = np.arange(max_seq_len, dtype=np.float32)
    freqs = np.outer(t, freqs)
    # Cos and Sin
    return np.cos(freqs), np.sin(freqs)


def apply_rope_np(x: np.ndarray, cos: np.ndarray, sin: np.ndarray) -> np.ndarray:
    # x shape: (seq_len, num_heads, d_head)
    seq_len, num_heads, d_head = x.shape
    x_reshaped = x.reshape(seq_len, num_heads, d_head // 2, 2)
    x1 = x_reshaped[..., 0]
    x2 = x_reshaped[..., 1]

    cos = cos[:seq_len, None, :]
    sin = sin[:seq_len, None, :]

    out1 = x1 * cos - x2 * sin
    out2 = x1 * sin + x2 * cos
    return np.stack([out1, out2], axis=-1).reshape(seq_len, num_heads, d_head)


class NumpyNairaModel:
    """Pure NumPy implementation of Naira Transformer for CPU execution."""

    def __init__(self, config: NairaModelConfig, weights: dict[str, np.ndarray] | None = None) -> None:
        self.config = config
        self.cos, self.sin = precompute_rope_freqs_np(config.d_head, config.max_seq_len, config.rope_theta)

        if weights is not None:
            self.weights = weights
        else:
            self.weights = self._init_random_weights()

    def _init_random_weights(self) -> dict[str, np.ndarray]:
        rng = np.random.RandomState(42)
        c = self.config
        scale = 0.02
        weights = {
            "tok_embeddings": rng.randn(c.vocab_size, c.d_model).astype(np.float32) * scale,
            "norm_weight": np.ones(c.d_model, dtype=np.float32),
            "output_weight": rng.randn(c.d_model, c.vocab_size).astype(np.float32) * scale,
        }

        for i in range(c.num_layers):
            weights[f"layer_{i}_attn_norm"] = np.ones(c.d_model, dtype=np.float32)
            weights[f"layer_{i}_q_proj"] = rng.randn(c.d_model, c.d_model).astype(np.float32) * scale
            weights[f"layer_{i}_k_proj"] = rng.randn(c.d_model, c.d_model).astype(np.float32) * scale
            weights[f"layer_{i}_v_proj"] = rng.randn(c.d_model, c.d_model).astype(np.float32) * scale
            weights[f"layer_{i}_out_proj"] = rng.randn(c.d_model, c.d_model).astype(np.float32) * scale

            weights[f"layer_{i}_ffn_norm"] = np.ones(c.d_model, dtype=np.float32)
            weights[f"layer_{i}_w1"] = rng.randn(c.d_model, c.d_ff).astype(np.float32) * scale
            weights[f"layer_{i}_w2"] = rng.randn(c.d_ff, c.d_model).astype(np.float32) * scale
            weights[f"layer_{i}_w3"] = rng.randn(c.d_model, c.d_ff).astype(np.float32) * scale

        return weights

    def forward(self, input_ids: list[int]) -> np.ndarray:
        """Compute logits for input token sequence. Returns shape: (seq_len, vocab_size)."""
        c = self.config
        seq_len = len(input_ids)
        h = self.weights["tok_embeddings"][input_ids]  # (seq_len, d_model)

        scale = 1.0 / math.sqrt(c.d_head)
        causal_mask = np.triu(np.full((seq_len, seq_len), -1e9, dtype=np.float32), k=1)

        for i in range(c.num_layers):
            # Attention block
            norm_h = rms_norm(h, self.weights[f"layer_{i}_attn_norm"], c.norm_eps)
            q = (norm_h @ self.weights[f"layer_{i}_q_proj"]).reshape(seq_len, c.num_heads, c.d_head)
            k = (norm_h @ self.weights[f"layer_{i}_k_proj"]).reshape(seq_len, c.num_kv_heads, c.d_head)
            v = (norm_h @ self.weights[f"layer_{i}_v_proj"]).reshape(seq_len, c.num_kv_heads, c.d_head)

            q = apply_rope_np(q, self.cos, self.sin)
            k = apply_rope_np(k, self.cos, self.sin)

            # Transpose: (num_heads, seq_len, d_head)
            q_t = np.transpose(q, (1, 0, 2))
            k_t = np.transpose(k, (1, 0, 2))
            v_t = np.transpose(v, (1, 0, 2))

            scores = (q_t @ np.transpose(k_t, (0, 2, 1))) * scale + causal_mask
            # Softmax
            exp_scores = np.exp(scores - np.max(scores, axis=-1, keepdims=True))
            attn_weights = exp_scores / np.sum(exp_scores, axis=-1, keepdims=True)

            attn_out = attn_weights @ v_t  # (num_heads, seq_len, d_head)
            attn_out = np.transpose(attn_out, (1, 0, 2)).reshape(seq_len, c.d_model)
            h = h + (attn_out @ self.weights[f"layer_{i}_out_proj"])

            # Feed-Forward SwiGLU block
            norm_ffn = rms_norm(h, self.weights[f"layer_{i}_ffn_norm"], c.norm_eps)
            ffn_out = swiglu(
                norm_ffn,
                self.weights[f"layer_{i}_w1"],
                self.weights[f"layer_{i}_w2"],
                self.weights[f"layer_{i}_w3"],
            )
            h = h + ffn_out

        final_norm = rms_norm(h, self.weights["norm_weight"], c.norm_eps)
        logits = final_norm @ self.weights["output_weight"]
        return logits
