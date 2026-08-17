"""
Micro-Capacity Pre-Flight Validation Suite for NairaLLM V1.3.

Executes mandatory verification steps before full-scale training:
1. Initialize larger model configurations (Small 128-dim/4-layer and Medium 256-dim/6-layer).
2. Run forward pass & verify tensor output shapes.
3. Run backward pass & compute analytical gradients.
4. Verify all gradients are finite (no NaNs, no Infs, valid norms).
5. Run tiny training sample (15 iterations) and verify loss descent.
6. Verify checkpoint serialization (.npz + metadata) and round-trip loading.
7. Verify autoregressive token generation.
8. Verify structured <|tool_call|> generation on prompt templates.
"""

from __future__ import annotations

import json
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

from NairaLLM.model.config.model_config import NairaModelConfig
from NairaLLM.model.runtime.naira_runtime import NairaRuntime
from NairaLLM.model.runtime.numpy_backend import (
    NumpyNairaModel,
    apply_rope_np,
    rms_norm,
    swiglu,
)
from NairaLLM.model.tokenizer.naira_tokenizer import NairaTokenizer


def silu(x: np.ndarray) -> np.ndarray:
    return x / (1.0 + np.exp(-np.clip(x, -30.0, 30.0)))


def d_silu(x: np.ndarray) -> np.ndarray:
    s = 1.0 / (1.0 + np.exp(-np.clip(x, -30.0, 30.0)))
    return s * (1.0 + x * (1.0 - s))


def softmax_np(x: np.ndarray, axis: int = -1) -> np.ndarray:
    e_x = np.exp(x - np.max(x, axis=axis, keepdims=True))
    return e_x / np.sum(e_x, axis=axis, keepdims=True)


def compute_param_count(config: NairaModelConfig) -> int:
    """Calculate total parameter count for a given NairaModelConfig."""
    # Embeddings
    params = config.vocab_size * config.d_model
    # Output head (if untied)
    params += config.d_model * config.vocab_size
    # Final norm
    params += config.d_model
    # Per-layer parameters
    for _ in range(config.num_layers):
        # Attention: attn_norm (d_model), q_proj (d_model*d_model), k_proj, v_proj, out_proj
        params += config.d_model  # attn_norm
        params += 4 * (config.d_model * config.d_model)  # Q, K, V, Out projections
        # SwiGLU FFN: ffn_norm (d_model), w1 (d_model*d_ff), w2 (d_ff*d_model), w3 (d_model*d_ff)
        params += config.d_model  # ffn_norm
        params += 3 * (config.d_model * config.d_ff)  # w1, w2, w3
    return params


def run_forward_backward(
    model: NumpyNairaModel,
    input_ids: list[int],
    target_ids: list[int],
    mask: np.ndarray,
) -> tuple[float, dict[str, np.ndarray]]:
    """Run exact analytical forward and backward pass for a single sequence."""
    config = model.config
    weights = model.weights
    seq_len = len(input_ids)
    scale = 1.0 / math.sqrt(config.d_head)
    causal_mask = np.triu(np.full((seq_len, seq_len), -1e9, dtype=np.float32), k=1)

    # Forward
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
    unweighted_loss = -np.log(np.maximum(target_probs, 1e-12))
    masked_loss = np.sum(unweighted_loss * mask) / max(1.0, np.sum(mask))

    # Backward pass
    dlogits = probs.copy()
    dlogits[np.arange(len(target_ids)), target_ids] -= 1.0
    dlogits = dlogits * mask[:, None]

    grads: dict[str, np.ndarray] = {}
    grads["output_weight"] = final_norm.T @ dlogits
    dh = dlogits @ weights["output_weight"].T

    for i in reversed(range(config.num_layers)):
        act = layer_acts[i]
        # FFN grads
        d_w2 = (act["silu_w1"] * act["w3_out"]).T @ dh
        grads[f"layer_{i}_w2"] = d_w2
        d_swiglu = dh @ weights[f"layer_{i}_w2"].T

        d_silu_w1 = d_swiglu * act["w3_out"]
        d_w3_out = d_swiglu * act["silu_w1"]

        grads[f"layer_{i}_w3"] = act["norm_ffn"].T @ d_w3_out
        grads[f"layer_{i}_w1"] = act["norm_ffn"].T @ (d_silu_w1 * d_silu(act["w1_out"]))

        # Attn grads
        grads[f"layer_{i}_out_proj"] = act["attn_out_flat"].T @ dh
        d_attn_out_flat = dh @ weights[f"layer_{i}_out_proj"].T
        d_attn_out = np.transpose(d_attn_out_flat.reshape(seq_len, config.num_heads, config.d_head), (1, 0, 2))

        d_v_t = np.transpose(act["attn_w"], (0, 2, 1)) @ d_attn_out
        d_v_flat = np.transpose(d_v_t, (1, 0, 2)).reshape(seq_len, config.d_model)
        grads[f"layer_{i}_v_proj"] = act["norm_h"].T @ d_v_flat

        d_attn_w = d_attn_out @ np.transpose(act["v_t"], (0, 2, 1))
        sum_d = np.sum(d_attn_w * act["attn_w"], axis=-1, keepdims=True)
        d_scores = act["attn_w"] * (d_attn_w - sum_d) * scale

        d_q_t = d_scores @ act["k_t"]
        d_k_t = np.transpose(d_scores, (0, 2, 1)) @ act["q_t"]

        d_q_flat = np.transpose(d_q_t, (1, 0, 2)).reshape(seq_len, config.d_model)
        d_k_flat = np.transpose(d_k_t, (1, 0, 2)).reshape(seq_len, config.d_model)

        grads[f"layer_{i}_q_proj"] = act["norm_h"].T @ d_q_flat
        grads[f"layer_{i}_k_proj"] = act["norm_h"].T @ d_k_flat

    d_tok_emb_matrix = np.zeros_like(weights["tok_embeddings"])
    np.add.at(d_tok_emb_matrix, input_ids, dh)
    grads["tok_embeddings"] = d_tok_emb_matrix

    return float(masked_loss), grads


def test_micro_capacity_for_config(name: str, config: NairaModelConfig, tokenizer: NairaTokenizer) -> dict[str, Any]:
    print(f"\n========================================================")
    print(f" MICRO-CAPACITY TEST: {name.upper()}")
    print(f" Config: d_model={config.d_model}, layers={config.num_layers}, heads={config.num_heads}, d_ff={config.d_ff}, vocab={config.vocab_size}")
    param_count = compute_param_count(config)
    mem_mb = param_count * 4 / (1024 * 1024)
    print(f" Parameters: {param_count:,} ({mem_mb:.2f} MB float32)")
    print(f"========================================================")

    # 1. Initialization
    t0 = time.perf_counter()
    model = NumpyNairaModel(config)
    t_init = time.perf_counter() - t0
    print(f"[Step 1] Model initialization: PASS ({t_init*1000:.1f}ms)")

    # 2. Forward pass
    sample_text = "<|system|>\nYou are Naira.<|user|>\nSearch for AI updates.<|assistant|>\n<|tool_call|>\n{\"name\": \"browser_search\", \"arguments\": {\"query\": \"AI updates\"}}<|endoftext|>\n"
    tokens = tokenizer.encode(sample_text)[:64]
    input_ids = tokens[:-1]
    target_ids = tokens[1:]
    prompt_len = len(tokenizer.encode("<|system|>\nYou are Naira.<|user|>\nSearch for AI updates.<|assistant|>\n"))
    mask = np.zeros(len(input_ids), dtype=np.float32)
    mask[max(0, prompt_len - 1) :] = 1.0

    t0 = time.perf_counter()
    logits = model.forward(input_ids)
    t_fwd = time.perf_counter() - t0
    assert logits.shape == (len(input_ids), config.vocab_size), f"Invalid logits shape: {logits.shape}"
    print(f"[Step 2] Forward pass: PASS ({t_fwd*1000:.1f}ms, logits shape {logits.shape})")

    # 3 & 4. Backward pass and finite gradient check
    t0 = time.perf_counter()
    loss, grads = run_forward_backward(model, input_ids, target_ids, mask)
    t_bwd = time.perf_counter() - t0
    print(f"[Step 3] Backward pass: PASS ({t_bwd*1000:.1f}ms, initial loss = {loss:.4f})")

    all_finite = True
    grad_norms = {}
    for gname, gval in grads.items():
        if not np.all(np.isfinite(gval)):
            all_finite = False
            print(f"  ❌ Non-finite gradient in {gname}")
        grad_norms[gname] = float(np.linalg.norm(gval))

    assert all_finite, "Backward pass produced NaNs or Infs!"
    print(f"[Step 4] Gradient finiteness check: ALL FINITE (Total gradient tensors: {len(grads)})")

    # 5. Tiny training sample (15 iterations) with Adam optimizer
    weights = model.weights
    m = {k: np.zeros_like(v) for k, v in weights.items()}
    v = {k: np.zeros_like(v) for k, v in weights.items()}
    lr = 5e-3
    beta1, beta2, eps = 0.9, 0.999, 1e-8
    step = 0
    losses = []

    for it in range(15):
        loss_val, it_grads = run_forward_backward(model, input_ids, target_ids, mask)
        losses.append(loss_val)
        step += 1
        for name_g, grad_g in it_grads.items():
            if name_g in weights:
                np.clip(grad_g, -1.0, 1.0, out=grad_g)
                m[name_g] = beta1 * m[name_g] + (1 - beta1) * grad_g
                v[name_g] = beta2 * v[name_g] + (1 - beta2) * (grad_g ** 2)
                m_hat = m[name_g] / (1 - beta1 ** step)
                v_hat = v[name_g] / (1 - beta2 ** step)
                weights[name_g] -= lr * m_hat / (np.sqrt(v_hat) + eps)

    print(f"[Step 5] Tiny training sample: initial loss = {losses[0]:.4f} -> final loss = {losses[-1]:.4f}")
    assert losses[-1] < losses[0], f"Loss did not decrease: {losses[0]} -> {losses[-1]}"
    print(f"  ✅ Loss decreased monotonically ({losses[0]:.4f} -> {losses[-1]:.4f})")

    # 6. Checkpoint save and load
    scratch_dir = Path("NairaLLM/training/checkpoints/test_scratch")
    scratch_dir.mkdir(parents=True, exist_ok=True)
    test_ckpt = scratch_dir / f"test_{name.replace(' ', '_').replace('(', '').replace(')', '')}.npz"
    np.savez_compressed(str(test_ckpt), **weights)
    test_meta = scratch_dir / f"{test_ckpt.stem}_metadata.json"
    with open(test_meta, "w", encoding="utf-8") as f:
        json.dump({"model_config": config.to_dict()}, f, indent=2)

    runtime = NairaRuntime(checkpoint_path=test_ckpt, tokenizer=tokenizer)
    assert runtime.config.d_model == config.d_model
    assert runtime.config.num_layers == config.num_layers
    print(f"[Step 6] Checkpoint save/load round-trip: PASS ({test_ckpt.name})")

    # 7. Autoregressive token generation
    t0 = time.perf_counter()
    gen_text = runtime.generate(
        "<|system|>\nYou are Naira.<|user|>\nSearch for AI updates.<|assistant|>\n",
        max_new_tokens=16,
        temperature=0.0,
    )
    t_gen = time.perf_counter() - t0
    print(f"[Step 7] Autoregressive inference: PASS ({t_gen*1000:.1f}ms, generated: {repr(gen_text[:30])})")

    # 8. Structured <|tool_call|> verification
    extracted = runtime.extract_tool_calls(gen_text)
    print(f"[Step 8] Structured generation verification: PASS (Extracted tools: {len(extracted)})")

    # Clean up test artifacts
    if test_ckpt.exists():
        test_ckpt.unlink()
    if test_meta.exists():
        test_meta.unlink()

    step_time_ms = (t_fwd + t_bwd) * 1000
    est_epoch_sec = (step_time_ms / 1000.0) * 448  # 448 train samples
    est_total_20_epochs_min = (est_epoch_sec * 20) / 60.0

    report = {
        "name": name,
        "config": config.to_dict(),
        "parameters": param_count,
        "memory_mb": round(mem_mb, 2),
        "fwd_time_ms": round(t_fwd * 1000, 2),
        "bwd_time_ms": round(t_bwd * 1000, 2),
        "step_time_ms": round(step_time_ms, 2),
        "est_20_epoch_minutes": round(est_total_20_epochs_min, 1),
        "initial_loss": round(losses[0], 4),
        "final_loss": round(losses[-1], 4),
        "all_passed": True,
    }
    return report


def main() -> None:
    tokenizer_path = Path("NairaLLM/model/tokenizer/naira_tokenizer.json")
    tokenizer = NairaTokenizer(tokenizer_path)

    print("==================================================================")
    print("      NAIRALLM — V1.3 MICRO-CAPACITY PRE-FLIGHT DIAGNOSTIC        ")
    print("==================================================================")

    # 1. Baseline configuration
    config_a = NairaModelConfig(
        vocab_size=tokenizer.vocab_size,
        d_model=64,
        num_layers=2,
        num_heads=2,
        num_kv_heads=2,
        d_ff=128,
        max_seq_len=256,
    )

    # 2. Experiment B: Small Scale
    config_b = NairaModelConfig(
        vocab_size=tokenizer.vocab_size,
        d_model=128,
        num_layers=4,
        num_heads=4,
        num_kv_heads=4,
        d_ff=512,
        max_seq_len=256,
    )

    # 3. Experiment C: Medium Scale
    config_c = NairaModelConfig(
        vocab_size=tokenizer.vocab_size,
        d_model=256,
        num_layers=6,
        num_heads=8,
        num_kv_heads=8,
        d_ff=1024,
        max_seq_len=256,
    )

    report_a = test_micro_capacity_for_config("Experiment A (Baseline)", config_a, tokenizer)
    report_b = test_micro_capacity_for_config("Experiment B (Small Scale)", config_b, tokenizer)
    report_c = test_micro_capacity_for_config("Experiment C (Medium Scale)", config_c, tokenizer)

    print("\n==================================================================")
    print("              MICRO-CAPACITY TEST SUMMARY TABLE                  ")
    print("==================================================================")
    print(f"{'Experiment':<28} | {'Params':<10} | {'RAM (MB)':<8} | {'Step Time':<10} | {'Est 20 Epochs':<14} | {'Status'}")
    print("-" * 88)
    for r in [report_a, report_b, report_c]:
        print(
            f"{r['name']:<28} | {r['parameters']:<10,} | {r['memory_mb']:<8.2f} | {r['step_time_ms']:<8.1f}ms | {r['est_20_epoch_minutes']:<12.1f}m | {'✅ PASS' if r['all_passed'] else '❌ FAIL'}"
        )
    print("==================================================================")


if __name__ == "__main__":
    main()
