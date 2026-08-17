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

    vocab_size: int = 1509
    d_model: int = 128
    num_layers: int = 4
    num_heads: int = 4
    num_kv_heads: int = 4
    d_ff: int = 512
    max_seq_len: int = 1024
    norm_eps: float = 1e-5
    rope_theta: float = 10000.0
    tie_embeddings: bool = True
    dropout: float = 0.0

    @property
    def d_head(self) -> int:
        return self.d_model // self.num_heads

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> NairaModelConfig:
        # Handle nested architecture/model dict if present
        source = data
        if "architecture" in data and isinstance(data["architecture"], dict):
            source = {**data, **data["architecture"]}
        elif "model" in data and isinstance(data["model"], dict):
            source = {**data, **data["model"]}
        
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
