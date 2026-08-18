"""
NairaTransformer: Lightweight Causal Decoder-Only Transformer Architecture.

Features:
- Rotary Position Embeddings (RoPE)
- RMSNorm pre-normalization
- SwiGLU Feed-Forward Networks
- Multi-Head Causal Attention with Key-Value Caching
- Cross-Entropy Loss with label masking
"""

from __future__ import annotations

import math
from typing import Any

from NairaLLM.model.config.model_config import NairaModelConfig

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    _HAS_TORCH = True
except ImportError:
    _HAS_TORCH = False


if _HAS_TORCH:

    class RMSNorm(nn.Module):
        """Root Mean Square Layer Normalization."""

        def __init__(self, dim: int, eps: float = 1e-5) -> None:
            super().__init__()
            self.eps = eps
            self.weight = nn.Parameter(torch.ones(dim))

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            norm = torch.rsqrt(x.pow(2).mean(-1, keepdim=True) + self.eps)
            return x * norm * self.weight

    def precompute_rope_freqs(dim: int, max_seq_len: int, theta: float = 10000.0) -> torch.Tensor:
        """Precompute complex frequencies for Rotary Position Embeddings."""
        freqs = 1.0 / (theta ** (torch.arange(0, dim, 2)[: (dim // 2)].float() / dim))
        t = torch.arange(max_seq_len, dtype=torch.float32)
        freqs = torch.outer(t, freqs)
        freqs_cis = torch.polar(torch.ones_like(freqs), freqs)  # complex64
        return freqs_cis

    def apply_rope(x: torch.Tensor, freqs_cis: torch.Tensor) -> torch.Tensor:
        """Apply rotary position embeddings to query or key tensors."""
        # x: (batch, seq_len, num_heads, d_head)
        x_complex = torch.view_as_complex(x.float().reshape(*x.shape[:-1], -1, 2))
        freqs_cis = freqs_cis[: x.shape[1], :].unsqueeze(0).unsqueeze(2)  # (1, seq_len, 1, d_head//2)
        x_rotated = torch.view_as_real(x_complex * freqs_cis).flatten(3)
        return x_rotated.type_as(x)

    class SwiGLU(nn.Module):
        """SwiGLU Gated Feed-Forward Network."""

        def __init__(self, d_model: int, d_ff: int) -> None:
            super().__init__()
            self.w1 = nn.Linear(d_model, d_ff, bias=False)
            self.w2 = nn.Linear(d_ff, d_model, bias=False)
            self.w3 = nn.Linear(d_model, d_ff, bias=False)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return self.w2(F.silu(self.w1(x)) * self.w3(x))

    class CausalSelfAttention(nn.Module):
        """Multi-Head Causal Self-Attention with RoPE and KV cache."""

        def __init__(self, config: NairaModelConfig) -> None:
            super().__init__()
            self.config = config
            self.d_model = config.d_model
            self.num_heads = config.num_heads
            self.num_kv_heads = config.num_kv_heads
            self.d_head = config.d_head
            self.scale = 1.0 / math.sqrt(self.d_head)

            self.q_proj = nn.Linear(self.d_model, self.num_heads * self.d_head, bias=False)
            self.k_proj = nn.Linear(self.d_model, self.num_kv_heads * self.d_head, bias=False)
            self.v_proj = nn.Linear(self.d_model, self.num_kv_heads * self.d_head, bias=False)
            self.out_proj = nn.Linear(self.num_heads * self.d_head, self.d_model, bias=False)

        def forward(
            self,
            x: torch.Tensor,
            freqs_cis: torch.Tensor,
            mask: torch.Tensor | None = None,
            kv_cache: tuple[torch.Tensor, torch.Tensor] | None = None,
        ) -> tuple[torch.Tensor, tuple[torch.Tensor, torch.Tensor]]:
            b_sz, seq_len, _ = x.shape

            q = self.q_proj(x).view(b_sz, seq_len, self.num_heads, self.d_head)
            k = self.k_proj(x).view(b_sz, seq_len, self.num_kv_heads, self.d_head)
            v = self.v_proj(x).view(b_sz, seq_len, self.num_kv_heads, self.d_head)

            q = apply_rope(q, freqs_cis)
            k = apply_rope(k, freqs_cis)

            if kv_cache is not None:
                k_prev, v_prev = kv_cache
                k = torch.cat([k_prev, k], dim=1)
                v = torch.cat([v_prev, v], dim=1)
            new_kv_cache = (k, v)

            # Transpose for attention: (batch, num_heads, seq_len, d_head)
            q = q.transpose(1, 2)
            k = k.transpose(1, 2)
            v = v.transpose(1, 2)

            if self.num_kv_heads != self.num_heads:
                # Grouped-Query Attention (GQA) head repeat
                repeat_factor = self.num_heads // self.num_kv_heads
                k = torch.repeat_interleave(k, repeat_factor, dim=1)
                v = torch.repeat_interleave(v, repeat_factor, dim=1)

            scores = torch.matmul(q, k.transpose(-2, -1)) * self.scale

            if mask is not None:
                scores = scores + mask

            attn_weights = F.softmax(scores, dim=-1, dtype=torch.float32).to(q.dtype)
            output = torch.matmul(attn_weights, v)
            output = output.transpose(1, 2).contiguous().view(b_sz, seq_len, -1)
            return self.out_proj(output), new_kv_cache

    class TransformerBlock(nn.Module):
        """Single Transformer Decoder Block."""

        def __init__(self, config: NairaModelConfig) -> None:
            super().__init__()
            self.attn_norm = RMSNorm(config.d_model, eps=config.norm_eps)
            self.attn = CausalSelfAttention(config)
            self.ffn_norm = RMSNorm(config.d_model, eps=config.norm_eps)
            self.ffn = SwiGLU(config.d_model, config.d_ff)

        def forward(
            self,
            x: torch.Tensor,
            freqs_cis: torch.Tensor,
            mask: torch.Tensor | None = None,
            kv_cache: tuple[torch.Tensor, torch.Tensor] | None = None,
        ) -> tuple[torch.Tensor, tuple[torch.Tensor, torch.Tensor]]:
            norm_x = self.attn_norm(x)
            attn_out, new_cache = self.attn(norm_x, freqs_cis, mask=mask, kv_cache=kv_cache)
            h = x + attn_out
            ffn_out = self.ffn(self.ffn_norm(h))
            out = h + ffn_out
            return out, new_cache

    class NairaTransformer(nn.Module):
        """Complete Naira Causal Decoder-Only Transformer."""

        def __init__(self, config: NairaModelConfig) -> None:
            super().__init__()
            self.config = config
            self.tok_embeddings = nn.Embedding(config.vocab_size, config.d_model)
            self.layers = nn.ModuleList([TransformerBlock(config) for _ in range(config.num_layers)])
            self.norm = RMSNorm(config.d_model, eps=config.norm_eps)
            self.output = nn.Linear(config.d_model, config.vocab_size, bias=False)

            if config.tie_embeddings:
                self.output.weight = self.tok_embeddings.weight

            # Precompute RoPE frequencies
            freqs = precompute_rope_freqs(config.d_head, config.max_seq_len, config.rope_theta)
            self.register_buffer("freqs_cis", freqs, persistent=False)

        def forward(
            self,
            input_ids: torch.Tensor,
            targets: torch.Tensor | None = None,
            kv_caches: list[tuple[torch.Tensor, torch.Tensor]] | None = None,
            start_pos: int = 0,
        ) -> tuple[torch.Tensor, torch.Tensor | None, list[tuple[torch.Tensor, torch.Tensor]]]:
            b_sz, seq_len = input_ids.shape
            h = self.tok_embeddings(input_ids)

            freqs_cis = self.freqs_cis[start_pos : start_pos + seq_len]

            # Causal mask for autoregressive attention
            mask = None
            if seq_len > 1:
                mask = torch.full((seq_len, seq_len), float("-inf"), device=input_ids.device)
                mask = torch.triu(mask, diagonal=1).unsqueeze(0).unsqueeze(0)

            new_kv_caches = []
            for i, layer in enumerate(self.layers):
                layer_cache = kv_caches[i] if kv_caches is not None else None
                h, new_cache = layer(h, freqs_cis, mask=mask, kv_cache=layer_cache)
                new_kv_caches.append(new_cache)

            h = self.norm(h)
            logits = self.output(h)

            loss = None
            if targets is not None:
                # Flatten logits and targets for cross-entropy
                loss = F.cross_entropy(
                    logits.view(-1, self.config.vocab_size),
                    targets.view(-1),
                    ignore_index=-100,
                )

            return logits, loss, new_kv_caches

        def count_parameters(self) -> int:
            return sum(p.numel() for p in self.parameters() if p.requires_grad)

else:
    # Lightweight stub if torch is loading
    class NairaTransformer:  # type: ignore
        def __init__(self, config: NairaModelConfig) -> None:
            self.config = config
