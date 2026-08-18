"""
Model Configuration dataclass for NairaLLM.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class NairaModelConfig:
    """Hyperparameters for the Naira Transformer model."""

    vocab_size: int = 4096
    d_model: int = 512
    num_layers: int = 8
    num_heads: int = 8
    num_kv_heads: int = 8
    d_ff: int = 1536
    max_seq_len: int = 2048
    norm_eps: float = 1e-5
    rope_theta: float = 10000.0
    tie_embeddings: bool = True
    dropout: float = 0.0

    @property
    def d_head(self) -> int:
        return self.d_model // self.num_heads

    def validate(self) -> None:
        """Validate hyperparameter invariants."""
        if self.d_model % self.num_heads != 0:
            raise ValueError(f"d_model ({self.d_model}) must be divisible by num_heads ({self.num_heads})")
        if self.num_heads % self.num_kv_heads != 0:
            raise ValueError(f"num_heads ({self.num_heads}) must be divisible by num_kv_heads ({self.num_kv_heads})")
        if self.d_ff <= 0:
            raise ValueError("d_ff must be positive")

    def calculate_exact_parameters(self) -> dict[str, int]:
        """Mathematically compute exact closed-form parameter counts."""
        self.validate()
        d = self.d_model
        h = self.num_heads
        h_kv = self.num_kv_heads
        d_h = self.d_head
        v = self.vocab_size
        l = self.num_layers
        ff = self.d_ff

        emb = v * d
        q_proj = d * (h * d_h)
        k_proj = d * (h_kv * d_h)
        v_proj = d * (h_kv * d_h)
        out_proj = (h * d_h) * d
        attn_norm = d

        w1 = d * ff
        w3 = d * ff
        w2 = ff * d
        ffn_norm = d

        layer_total = q_proj + k_proj + v_proj + out_proj + attn_norm + w1 + w3 + w2 + ffn_norm
        all_layers = layer_total * l
        final_norm = d
        lm_head = 0 if self.tie_embeddings else (v * d)

        total_tied = emb + all_layers + final_norm
        total_untied = emb + all_layers + final_norm + (v * d)

        return {
            "embedding": emb,
            "q_proj_per_layer": q_proj,
            "k_proj_per_layer": k_proj,
            "v_proj_per_layer": v_proj,
            "out_proj_per_layer": out_proj,
            "attn_norm_per_layer": attn_norm,
            "swiglu_w1_per_layer": w1,
            "swiglu_w3_per_layer": w3,
            "swiglu_w2_per_layer": w2,
            "ffn_norm_per_layer": ffn_norm,
            "single_layer_total": layer_total,
            "all_layers_total": all_layers,
            "final_norm": final_norm,
            "lm_head": lm_head,
            "total_parameters_tied": total_tied,
            "total_parameters_untied": total_untied,
        }

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> NairaModelConfig:
        # Handle nested architecture/model dict if present
        source = dict(data)
        if "architecture" in data and isinstance(data["architecture"], dict):
            source = {**source, **data["architecture"]}
        elif "model" in data and isinstance(data["model"], dict):
            source = {**source, **data["model"]}
        
        # Pull vocab_size from tokenizer config if present
        if "tokenizer" in data and isinstance(data["tokenizer"], dict) and "vocab_size" in data["tokenizer"]:
            source.setdefault("vocab_size", data["tokenizer"]["vocab_size"])

        return cls(**{k: v for k, v in source.items() if k in cls.__dataclass_fields__})

    def save(self, file_path: str | Path) -> None:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, file_path: str | Path) -> NairaModelConfig:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def load_canonical_v1(cls) -> NairaModelConfig:
        canonical_path = Path(__file__).resolve().parent.parent.parent / "configs" / "final_nairallm_v1.json"
        return cls.load(canonical_path)

