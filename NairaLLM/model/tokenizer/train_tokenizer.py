"""
Train and save the NairaLLM Byte-Level BPE Tokenizer.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from NairaLLM.dataset.dataset_manager import DatasetManager
from NairaLLM.model.tokenizer.naira_tokenizer import NairaTokenizer


def gather_training_corpus() -> list[str]:
    dm = DatasetManager()
    reviewed_file = dm.reviewed_dir / "v1_1_expanded_dataset.jsonl"
    if not reviewed_file.exists():
        reviewed_file = dm.reviewed_dir / "initial_dataset.jsonl"
    samples = dm.load_jsonl(reviewed_file)

    corpus: list[str] = []

    # Dataset samples
    for sample in samples:
        corpus.append(sample.system_prompt)
        for msg in sample.conversations:
            corpus.append(msg.content)
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    corpus.append(f"<|tool_call|>\n{json.dumps({'name': tc.name, 'arguments': tc.arguments})}")

    # Additional representative Naira OS terms & multilingual strings
    extra_texts = [
        "Naira OS is an intelligent operating system built with modular Python architecture.",
        "नमस्ते, मैं आपकी सहायता के लिए तैयार हूँ।",
        "Aapka system volume 50% pe set ho gaya hai.",
        "browser_search(query='python documentation', max_results=5)",
        "browser_navigate(url='https://github.com')",
        "remember_fact(topic='user_preference', fact='likes dark mode')",
        "search_memory(query='dark mode', limit=5)",
        "pc_mouse(action='click', x=100, y=200)",
        "pc_keyboard(action='type_text', text='hello world')",
        "pc_system_settings(setting='volume', value=75)",
        "<|thought|>\nUser requested system status. Tool: None needed.\n<|plan|>\n1. Report status.",
        "{\"status\": \"success\", \"output\": \"Tool executed successfully.\"}",
        "{\"status\": \"error\", \"error\": \"Command failed.\"}",
        "def execute_task(task_description: str, context: dict | None = None) -> ToolResult:",
        "async def generate(self, system_prompt: str, messages: list[Message]) -> Any:",
        "/backend/modules/tools/ports/tool_provider.py",
        "/backend/modules/memory/memory_module.py",
        "/backend/runtime/response_pipeline.py",
    ]
    corpus.extend(extra_texts)
    return corpus


def main() -> None:
    corpus = gather_training_corpus()
    print(f"Gathered {len(corpus)} text snippets for tokenizer training.")

    tokenizer = NairaTokenizer()
    tokenizer.train_on_corpus(corpus, vocab_size=2048, min_frequency=1)

    save_path = Path(__file__).resolve().parent / "naira_tokenizer.json"
    tokenizer.save(save_path)
    print(f"Trained NairaTokenizer with vocab_size={tokenizer.vocab_size}. Saved to {save_path}")

    # Verify encoding/decoding
    test_cases = [
        "Good morning Naira!",
        "नमस्ते नायरा, सिस्टम का हाल बताओ।",
        "Volume 40% pe kar do please.",
        "<|tool_call|>\n{\"name\": \"pc_system_settings\", \"arguments\": {\"setting\": \"volume\", \"value\": 40}}",
    ]

    print("\n--- Tokenizer Test Run ---")
    for text in test_cases:
        ids = tokenizer.encode(text)
        decoded = tokenizer.decode(ids)
        print(f"Original: {text}")
        print(f"Encoded IDs ({len(ids)} tokens): {ids}")
        print(f"Decoded:  {decoded}")
        assert decoded.strip() == text.strip(), f"Mismatch: '{decoded}' != '{text}'"
        print("  -> Match: OK\n")


if __name__ == "__main__":
    main()
