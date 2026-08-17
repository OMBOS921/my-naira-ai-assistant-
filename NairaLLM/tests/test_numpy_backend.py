"""
Unit tests for Pure NumPy NairaLLM Backend.
"""

from __future__ import annotations

import numpy as np
import pytest

from NairaLLM.model.config.model_config import NairaModelConfig
from NairaLLM.model.runtime.numpy_backend import NumpyNairaModel, rms_norm, swiglu


def test_rms_norm() -> None:
    x = np.array([[1.0, 2.0, 3.0]], dtype=np.float32)
    weight = np.ones(3, dtype=np.float32)
    out = rms_norm(x, weight)
    assert out.shape == (1, 3)
    assert np.all(np.isfinite(out))


def test_swiglu() -> None:
    x = np.random.randn(2, 64).astype(np.float32)
    w1 = np.random.randn(64, 128).astype(np.float32)
    w2 = np.random.randn(128, 64).astype(np.float32)
    w3 = np.random.randn(64, 128).astype(np.float32)
    out = swiglu(x, w1, w2, w3)
    assert out.shape == (2, 64)
    assert np.all(np.isfinite(out))


def test_numpy_model_forward() -> None:
    config = NairaModelConfig(vocab_size=100, d_model=32, num_layers=2, num_heads=2, num_kv_heads=2, d_ff=64)
    model = NumpyNairaModel(config)
    input_ids = [1, 5, 20, 33]
    logits = model.forward(input_ids)
    assert logits.shape == (4, 100)
    assert np.all(np.isfinite(logits))
