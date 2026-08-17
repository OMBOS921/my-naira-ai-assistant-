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

    vocab_size: int = 2048
    d_model: int = 256
    num_layers: int = 6
    num_heads: int = 8
    num_kv_heads: int = 8
    d_ff: int = 684
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
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

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
