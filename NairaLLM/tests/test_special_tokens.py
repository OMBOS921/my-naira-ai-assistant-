"""
Unit Tests for Special Token Preservation in NairaLLM.

Verifies that special tokens:
<|system|>, <|user|>, <|assistant|>, <|tool_call|>, <|tool_result|>, <|plan|>, <|verify|>, <|endoftext|>
maintain stable, single-token integer IDs and 100% roundtrip fidelity between training and inference.
"""

from pathlib import Path
from NairaLLM.model.tokenizer.naira_tokenizer import NairaTokenizer, SPECIAL_TOKENS


def test_special_token_id_stability():
    tok = NairaTokenizer(Path("NairaLLM/model/tokenizer/naira_tokenizer.json"))
    
    expected_ids = {
        "<|pad|>": 0,
        "<|endoftext|>": 1,
        "<|system|>": 2,
        "<|user|>": 3,
        "<|assistant|>": 4,
        "<|context|>": 5,
        "<|intent|>": 6,
        "<|plan|>": 7,
        "<|tool_call|>": 8,
        "<|tool_result|>": 9,
        "<|verify|>": 10,
        "<|recover|>": 11,
        "<|no_tool|>": 12,
        "<|proactive|>": 13,
        "<|final|>": 14,
        "<|thought|>": 15,
        "<|unk|>": 16,
    }
    
    for token_str, expected_id in expected_ids.items():
        encoded = tok.encode(token_str)
        assert len(encoded) == 1, f"Token {token_str} must encode to a single ID, got {encoded}"
        assert encoded[0] == expected_id, f"Token {token_str} ID mismatch: expected {expected_id}, got {encoded[0]}"
        
        decoded = tok.decode(encoded, skip_special_tokens=False)
        assert decoded == token_str, f"Token {token_str} decode mismatch: expected {token_str}, got {decoded}"


def test_prompt_special_token_transitions():
    tok = NairaTokenizer(Path("NairaLLM/model/tokenizer/naira_tokenizer.json"))
    
    train_prompt = (
        "<|system|>\nYou are Naira.\n"
        "<|user|>\nTurn down volume.\n"
        "<|assistant|>\n"
        "<|tool_call|>\n{\"name\": \"pc_system_settings\", \"arguments\": {\"setting\": \"volume\", \"value\": 20}}\n"
        "<|endoftext|>"
    )
    
    tokens = tok.encode(train_prompt)
    assert 2 in tokens, "Must contain <|system|> ID 2"
    assert 3 in tokens, "Must contain <|user|> ID 3"
    assert 4 in tokens, "Must contain <|assistant|> ID 4"
    assert 8 in tokens, "Must contain <|tool_call|> ID 8"
    assert 1 in tokens, "Must contain <|endoftext|> ID 1"
    
    decoded = tok.decode(tokens, skip_special_tokens=False)
    assert "<|tool_call|>" in decoded
    assert "pc_system_settings" in decoded


def test_v1_4_structured_cognition_transitions():
    tok = NairaTokenizer(Path("NairaLLM/model/tokenizer/naira_tokenizer.json"))
    
    prompt = (
        "<|system|>\nYou are Naira.\n"
        "<|user|>\nBoss, volume thoda kam kar do\n"
        "<|assistant|>\n"
        "<|intent|>\nsystem_volume_change\n"
        "<|tool_call|>\npc_system_settings\n"
        "{\"setting\": \"volume\", \"value\": 20}\n"
        "<|endoftext|>"
    )
    
    tokens = tok.encode(prompt)
    assert 6 in tokens, "Must contain <|intent|> ID 6"
    assert 8 in tokens, "Must contain <|tool_call|> ID 8"
    assert 1 in tokens, "Must contain <|endoftext|> ID 1"
    
    decoded = tok.decode(tokens, skip_special_tokens=False)
    assert "<|intent|>" in decoded
    assert "system_volume_change" in decoded
    assert "<|tool_call|>" in decoded
    assert "pc_system_settings" in decoded

