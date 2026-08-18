"""
Train and save the NairaLLM Byte-Level BPE Tokenizer.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

workspace_root = Path(__file__).resolve().parent.parent.parent.parent
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from NairaLLM.model.tokenizer.naira_tokenizer import NairaTokenizer


def gather_training_corpus() -> list[str]:
    corpus: list[str] = []
    base = Path(__file__).resolve().parent.parent.parent / "dataset" / "final"

    files = [
        base / "A_semantic" / "dataset_a_semantic.jsonl",
        base / "B_naira_capability" / "dataset_b_all_capabilities.jsonl",
        base / "C_behavior" / "dataset_c_behavior.jsonl",
    ]

    for fpath in files:
        if fpath.exists():
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        item = json.loads(line)
                        if "text" in item and item["text"]:
                            corpus.append(item["text"])
                        if "conversations" in item:
                            for msg in item["conversations"]:
                                if "content" in msg and msg["content"]:
                                    corpus.append(msg["content"])
                    except Exception:
                        pass

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
    tokenizer.train_on_corpus(corpus, vocab_size=4096, min_frequency=1)

    save_path = Path(__file__).resolve().parent / "naira_tokenizer.json"
    tokenizer.save(save_path)
    print(f"Trained NairaTokenizer with vocab_size={tokenizer.vocab_size}. Saved to {save_path}")

    # Verify encoding/decoding
    test_cases = [
        "Good morning Naira!",
        "नमस्ते नायरा, सिस्टम का हाल बताओ।",
        "Volume 40% pe kar do please.",
        "<|tool_call|>\n{\"name\": \"pc_system_settings\", \"arguments\": {\"setting\": \"volume\", \"value\": 40}}",
        "<|intent|>\n{\"category\": \"coding\", \"requires_tool\": false}",
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
