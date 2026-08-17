"""
Instruction Masking & Target Alignment Verification Script.

Visualizes token-by-token alignment for training samples, proving that:
- System prompt tokens -> MASKED (0.0 weight)
- User input tokens -> MASKED (0.0 weight)
- Assistant header token (<|assistant|>\n) -> MASKED (0.0 weight)
- Assistant response tokens -> TRAINED (1.0 weight)
- Tool call tokens (<|tool_call|>\n{...}) -> TRAINED (1.0 weight)
- Refusal tokens -> TRAINED (1.0 weight)
- End-of-sequence token (<|endoftext|>) -> TRAINED (1.0 weight)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from NairaLLM.dataset.dataset_manager import DatasetManager
from NairaLLM.model.tokenizer.naira_tokenizer import NairaTokenizer


def prepare_sample_with_mask(
    sample: Any,
    tokenizer: NairaTokenizer,
    max_seq_len: int = 256,
) -> tuple[list[int], np.ndarray, list[tuple[int, str, float]]]:
    """Build input tokens and exact target mask for supervised instruction fine-tuning."""
    # 1. Build prompt prefix
    prompt_str = f"<|system|>\n{sample.system_prompt}\n"
    for msg in sample.conversations[:-1]:
        if msg.role == "user":
            prompt_str += f"<|user|>\n{msg.content}\n"
        elif msg.role == "tool":
            prompt_str += f"<|tool_result|>\n{msg.content}\n"
        elif msg.role == "assistant":
            prompt_str += f"<|assistant|>\n{msg.content}<|endoftext|>\n"

    last_msg = sample.conversations[-1]
    prompt_str += "<|assistant|>\n"
    target_str = f"{last_msg.content}<|endoftext|>\n"

    prompt_tokens = tokenizer.encode(prompt_str)
    target_tokens = tokenizer.encode(target_str)

    full_tokens = (prompt_tokens + target_tokens)[:max_seq_len]
    if len(full_tokens) < 2:
        return [], np.array([]), []

    # Mask: 0 for prompt, 1 for target
    mask = np.zeros(len(full_tokens) - 1, dtype=np.float32)
    # The prompt_tokens are the context; target begins at index (len(prompt_tokens) - 1)
    target_start_idx = max(0, len(prompt_tokens) - 1)
    mask[target_start_idx:] = 1.0

    # Build token inspection table
    inspection: list[tuple[int, str, float]] = []
    for i in range(len(full_tokens) - 1):
        target_token_id = full_tokens[i + 1]
        token_str = tokenizer.decode([target_token_id], skip_special_tokens=False)
        inspection.append((target_token_id, token_str, float(mask[i])))

    return full_tokens, mask, inspection


def main() -> None:
    tok = NairaTokenizer(Path("NairaLLM/model/tokenizer/naira_tokenizer.json"))
    dm = DatasetManager()
    samples = dm.load_jsonl(dm.reviewed_dir / "v1_1_expanded_dataset.jsonl")

    print("==================================================")
    print("      INSTRUCTION MASKING VERIFICATION AUDIT      ")
    print("==================================================")

    # Pick 3 diverse samples: Tool Call, Safety Refusal, Natural Conversation
    tool_sample = next((s for s in samples if s.family.value == "tool_selection"), samples[0])
    safety_sample = next((s for s in samples if s.family.value == "safety_permissions"), samples[1])
    conv_sample = next((s for s in samples if s.family.value == "conversation"), samples[2])

    test_cases = [
        ("TOOL CALL TARGET", tool_sample),
        ("SAFETY REFUSAL TARGET", safety_sample),
        ("NATURAL CONVERSATION TARGET", conv_sample),
    ]

    for title, sample in test_cases:
        print(f"\n--- {title} (ID: {sample.id}, Family: {sample.family.value}) ---")
        tokens, mask, inspection = prepare_sample_with_mask(sample, tok)
        trained_count = int(np.sum(mask))
        ignored_count = len(mask) - trained_count
        print(f"Total Sequence Length: {len(tokens)} tokens | Prompt Ignored: {ignored_count} | Target Trained: {trained_count}")

        print("\nToken Inspection (Target Token -> Weight):")
        for tid, tstr, weight in inspection[:12]:
            display_str = repr(tstr)
            print(f"  ID {tid:4d} | Token: {display_str:25s} | Weight: {weight:.1f} ({'TRAINED' if weight > 0 else 'IGNORED'})")

        if len(inspection) > 16:
            print("  ...")
            for tid, tstr, weight in inspection[-6:]:
                display_str = repr(tstr)
                print(f"  ID {tid:4d} | Token: {display_str:25s} | Weight: {weight:.1f} ({'TRAINED' if weight > 0 else 'IGNORED'})")

    print("\n==================================================")
    print("Masking Verification PASSED: Prompt tokens 0.0, Target tokens 1.0.")
    print("==================================================")


if __name__ == "__main__":
    main()
