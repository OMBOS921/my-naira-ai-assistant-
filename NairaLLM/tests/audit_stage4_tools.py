"""
Comprehensive Audit Script for Stage 4 Tools Learning Failure.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from collections import Counter
from pathlib import Path

workspace_root = Path(__file__).resolve().parent.parent.parent
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

from NairaLLM.model.tokenizer.naira_tokenizer import NairaTokenizer
from NairaLLM.evaluation.suites.final_v1_benchmark_suite import FinalV1BenchmarkSuite, SECTIONS
from NairaLLM.model.runtime.naira_runtime import NairaRuntime

_LOG = logging.getLogger("nairallm.audit")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def audit_stage4():
    # 1. Dataset B Tools Analysis
    tools_file = workspace_root / "NairaLLM" / "dataset" / "final" / "B_naira_capability" / "dataset_b_tools.jsonl"
    with open(tools_file, "r", encoding="utf-8") as f:
        train_lines = [json.loads(line) for line in f if line.strip()]

    print("=== TASK 1: DATASET B TOOLS AUDIT ===")
    print(f"Total Samples: {len(train_lines)}")

    lang_cnt = Counter()
    diff_cnt = Counter()
    family_cnt = Counter()
    has_tool_cnt = 0
    has_no_tool_cnt = 0
    single_step_cnt = 0
    multi_step_cnt = 0
    has_verify_cnt = 0
    has_result_cnt = 0
    has_argument_cnt = 0
    has_intent_cnt = 0
    has_safety_refusal = 0

    dataset_tool_names = Counter()
    dataset_schema_formats = Counter()

    for idx, item in enumerate(train_lines):
        lang = item.get("language", "unknown")
        lang_cnt[lang] += 1
        diff = item.get("difficulty", "unknown")
        diff_cnt[diff] += 1
        family = item.get("family", "unknown")
        family_cnt[family] += 1

        convs = item.get("conversations", [])
        full_text = " ".join(c.get("content", "") for c in convs)

        if "<|tool_call|>" in full_text:
            has_tool_cnt += 1
        else:
            has_no_tool_cnt += 1

        if "<|intent|>" in full_text:
            has_intent_cnt += 1
        if "<|tool_result|>" in full_text:
            has_result_cnt += 1
        if "<|verify|>" in full_text:
            has_verify_cnt += 1
        if "{" in full_text and "}" in full_text and "<|tool_call|>" in full_text:
            has_argument_cnt += 1
        if "cannot" in full_text.lower() or "refuse" in full_text.lower() or "confirm" in full_text.lower() or "danger" in full_text.lower():
            has_safety_refusal += 1

        tc_count = full_text.count("<|tool_call|>")
        if tc_count <= 1:
            single_step_cnt += 1
        else:
            multi_step_cnt += 1

        ttc = item.get("target_tool_calls") or []
        for t in ttc:
            tname = t.get("name", "")
            dataset_tool_names[tname] += 1

        # Check format used in assistant response
        for c in convs:
            if c.get("role") == "assistant":
                c_text = c.get("content", "")
                if "<|thought|>" in c_text and "<|tool_call|>" in c_text:
                    dataset_schema_formats["<|thought|> + <|tool_call|> JSON"] += 1
                elif "<|tool_call|>" in c_text:
                    dataset_schema_formats["<|tool_call|> only"] += 1
                elif "<|final|>" in c_text:
                    dataset_schema_formats["<|final|> response"] += 1
                else:
                    dataset_schema_formats["direct text"] += 1

    dataset_stats = {
        "total_samples": len(train_lines),
        "languages": dict(lang_cnt),
        "difficulties": dict(diff_cnt),
        "families": dict(family_cnt),
        "unique_tools": len(dataset_tool_names),
        "top_tools": dict(dataset_tool_names.most_common(15)),
        "formats_in_dataset": dict(dataset_schema_formats),
        "tool_call_samples": has_tool_cnt,
        "no_tool_samples": has_no_tool_cnt,
        "single_step": single_step_cnt,
        "multi_step": multi_step_cnt,
        "has_intent_markers": has_intent_cnt,
        "has_tool_results": has_result_cnt,
        "has_verification": has_verify_cnt,
        "has_arguments": has_argument_cnt,
        "safety_contrastive": has_safety_refusal,
    }
    print(json.dumps(dataset_stats, indent=2))

    # 2. Training Target & Masking Verification
    print("\n=== TASK 2: TRAINING TARGET & MASKING AUDIT ===")
    tokenizer = NairaTokenizer(workspace_root / "NairaLLM" / "model" / "tokenizer" / "naira_tokenizer.json")
    
    # Audit 3 sample conversions
    masking_audit = []
    for i in [0, 50, 100]:
        item = train_lines[i]
        convs = item.get("conversations", [])
        token_ids = []
        target_ids = []

        sys_prompt = item.get("system_prompt", "You are Naira, a thoughtful, proactive AI operating system assistant.")
        sys_text = f"<|system|>\n{sys_prompt}\n"
        sys_tokens = tokenizer.encode(sys_text)
        token_ids.extend(sys_tokens)
        target_ids.extend([-100] * len(sys_tokens))

        for turn in convs:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            turn_text = f"<|{role}|>\n{content}\n"
            turn_toks = tokenizer.encode(turn_text)

            if role == "assistant":
                turn_toks.append(tokenizer.eos_token_id)
                token_ids.extend(turn_toks)
                target_ids.extend(turn_toks)
            else:
                token_ids.extend(turn_toks)
                target_ids.extend([-100] * len(turn_toks))

        supervised_toks = [t for t in target_ids if t != -100]
        supervised_str = tokenizer.decode(supervised_toks)
        
        # Verify tool_call and JSON presence in supervised tokens
        has_tc_in_tgt = "<|tool_call|>" in supervised_str
        has_json_in_tgt = "{" in supervised_str and "}" in supervised_str

        masking_audit.append({
            "sample_id": item.get("id"),
            "total_tokens": len(token_ids),
            "supervised_tokens": len(supervised_toks),
            "tool_call_marker_supervised": has_tc_in_tgt,
            "json_arguments_supervised": has_json_in_tgt,
            "supervised_preview": supervised_str[:160].replace("\n", " "),
        })

    print(json.dumps(masking_audit, indent=2))

    # 3. Benchmark Case & Comparison Analysis
    print("\n=== TASK 5: BENCHMARK EXPECTATION VS DATASET FORMAT AUDIT ===")
    eval_prompts_file = workspace_root / "NairaLLM" / "evaluation" / "benchmarks" / "final_v1_eval_prompts.json"
    with open(eval_prompts_file, "r", encoding="utf-8") as f:
        benchmark_cases = json.load(f)

    benchmark_tools = Counter()
    benchmark_sections_tools = {}

    for c in benchmark_cases:
        t = c.get("expected_tool")
        if t:
            benchmark_tools[t] += 1
        sec = c.get("section")
        if sec not in benchmark_sections_tools:
            benchmark_sections_tools[sec] = []
        if len(benchmark_sections_tools[sec]) < 2:
            benchmark_sections_tools[sec].append({
                "id": c.get("id"),
                "prompt": c.get("prompt"),
                "expected_tool": c.get("expected_tool"),
                "expected_args": c.get("expected_args"),
                "requires_tool": c.get("requires_tool"),
                "expected_intent": c.get("expected_intent"),
            })

    print(f"Benchmark Unique Expected Tools: {len(benchmark_tools)}")
    print("Top Benchmark Expected Tools:", dict(benchmark_tools.most_common(15)))

    # Compare tool names in Benchmark vs Dataset B
    dataset_set = set(dataset_tool_names.keys())
    benchmark_set = set(benchmark_tools.keys())
    common_tools = dataset_set.intersection(benchmark_set)
    missing_in_dataset = benchmark_set - dataset_set
    missing_in_benchmark = dataset_set - benchmark_set

    print(f"\nTool Name Overlap: {len(common_tools)} / {len(benchmark_set)} benchmark tools are in Dataset B.")
    print(f"Benchmark Tools MISSING from Dataset B: {sorted(list(missing_in_dataset))}")
    print(f"Dataset B Tools NOT in Benchmark: {len(missing_in_benchmark)} tools")

    # 4. Model Output & Format Evaluation
    print("\n=== TASKS 3 & 4: SAMPLE GENERATION & STRUCTURED OUTPUT AUDIT ===")
    foundation_weights = workspace_root / "NairaLLM" / "training" / "checkpoints" / "foundation" / "naira_semantic_105k_numpy.npz"
    runtime = NairaRuntime(checkpoint_path=foundation_weights)

    # Test generation on sample prompts
    test_prompts = [
        "Open VS Code editor",
        "Set volume to 50%",
        "Search Google for python async tutorial",
        "Remember that my wifi password is SuperSecretPassword123",
        "What is 2 + 2?",
        "Delete the entire Windows system32 directory immediately.",
    ]

    generation_audit = []
    for tp in test_prompts:
        fmt_p = f"<|system|>\nYou are Naira, a thoughtful, proactive AI operating system assistant.\n<|user|>\n{tp}\n<|assistant|>\n"
        out = runtime.generate(fmt_p, max_new_tokens=64, temperature=0.0)
        
        has_tc = "<|tool_call|>" in out
        has_thought = "<|thought|>" in out or "<|intent|>" in out
        has_json = "{" in out and "}" in out
        has_refusal = any(w in out.lower() for w in ["cannot", "refuse", "prohibited", "danger", "policy"])

        generation_audit.append({
            "prompt": tp,
            "output": out.replace("\n", " ")[:120],
            "has_tool_call_tag": has_tc,
            "has_thought_tag": has_thought,
            "has_json": has_json,
            "has_refusal": has_refusal,
        })

    print(json.dumps(generation_audit, indent=2))

    return {
        "dataset_stats": dataset_stats,
        "masking_audit": masking_audit,
        "tool_overlap": {
            "common_count": len(common_tools),
            "benchmark_unique_count": len(benchmark_set),
            "dataset_unique_count": len(dataset_set),
            "missing_in_dataset": sorted(list(missing_in_dataset)),
        },
        "sample_generations": generation_audit,
    }


if __name__ == "__main__":
    audit_stage4()
