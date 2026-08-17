"""
Unit tests for NairaTokenizer.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from NairaLLM.model.tokenizer.naira_tokenizer import NairaTokenizer


@pytest.fixture
def tokenizer() -> NairaTokenizer:
    path = Path("NairaLLM/model/tokenizer/naira_tokenizer.json")
    if not path.exists():
        # Train base on fly if needed
        t = NairaTokenizer()
        t.train_on_corpus(["Hello world", "नमस्ते नायरा", "Volume 50%"], vocab_size=256)
        return t
    return NairaTokenizer(path)


def test_special_tokens(tokenizer: NairaTokenizer) -> None:
    assert tokenizer.pad_token_id == 0
    assert tokenizer.eos_token_id == 1


def test_multilingual_roundtrip(tokenizer: NairaTokenizer) -> None:
    samples = [
        "Good morning Naira!",
        "नमस्ते नायरा, सिस्टम का हाल बताओ।",
        "Volume 40% pe kar do please.",
        "<|tool_call|>\n{\"name\": \"pc_system_settings\", \"arguments\": {\"setting\": \"volume\", \"value\": 40}}",
    ]

    for sample in samples:
        token_ids = tokenizer.encode(sample)
        assert len(token_ids) > 0
        decoded = tokenizer.decode(token_ids)
        assert decoded.strip() == sample.strip()
