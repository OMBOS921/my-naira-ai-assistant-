"""
Comprehensive V1 vs V1.1 Model Generalization Comparison Suite.

Evaluates both NairaLLM Prototype V1 and NairaLLM V1.1 checkpoints
on the exact same 55 unseen test cases and generates side-by-side comparative analysis.

Outputs:
evaluation/results/v1_vs_v1_1_report.json
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from NairaLLM.evaluation.suites.model_generalization_suite import (
    ModelGeneralizationSuite,
    UNSEEN_TEST_CASES,
)
from NairaLLM.integration.adapter.naira_llm_adapter import NairaLLMAdapter
from NairaLLM.model.runtime.naira_runtime import NairaRuntime

_LOG = logging.getLogger("nairallm.compare_v1_v1_1")


async def run_comparison() -> dict[str, Any]:
    v1_ckpt = Path("NairaLLM/training/checkpoints/numpy_model_v1_backup.npz")
    if not v1_ckpt.exists():
        v1_ckpt = Path("NairaLLM/training/checkpoints/numpy_model.npz")

    v1_1_ckpt = Path("NairaLLM/training/checkpoints/numpy_model_v1_1.npz")
    if not v1_1_ckpt.exists():
        v1_1_ckpt = Path("NairaLLM/training/checkpoints/numpy_model.npz")

    print("==================================================")
    print("      NairaLLM V1 vs V1.1 Generalization Benchmark")
    print("==================================================")

    # 1. Evaluate V1
    print(f"\n[1/2] Evaluating Prototype V1 Checkpoint ({v1_ckpt.name})...")
    v1_runtime = NairaRuntime(checkpoint_path=v1_ckpt)
    v1_adapter = NairaLLMAdapter(runtime=v1_runtime)
    v1_suite = ModelGeneralizationSuite(adapter=v1_adapter)
    v1_results = await v1_suite.run_suite()
    print(f"  -> V1 Accuracy on Unseen Tests: {v1_results['passed_tests']}/{v1_results['total_unseen_tests']} ({round(v1_results['accuracy']*100, 1)}%)")

    # 2. Evaluate V1.1
    print(f"\n[2/2] Evaluating Expanded V1.1 Checkpoint ({v1_1_ckpt.name})...")
    v1_1_runtime = NairaRuntime(checkpoint_path=v1_1_ckpt)
    v1_1_adapter = NairaLLMAdapter(runtime=v1_1_runtime)
    v1_1_suite = ModelGeneralizationSuite(adapter=v1_1_adapter)
    v1_1_results = await v1_1_suite.run_suite()
    print(f"  -> V1.1 Accuracy on Unseen Tests: {v1_1_results['passed_tests']}/{v1_1_results['total_unseen_tests']} ({round(v1_1_results['accuracy']*100, 1)}%)")

    # 3. Build Comparative Analysis
    all_categories = sorted(
        list(set(list(v1_results["category_performance"].keys()) + list(v1_1_results["category_performance"].keys())))
    )
    all_languages = sorted(
        list(set(list(v1_results["language_performance"].keys()) + list(v1_1_results["language_performance"].keys())))
    )

    category_comparison = {}
    for cat in all_categories:
        v1_c = v1_results["category_performance"].get(cat, {"passed": 0, "total": 0, "accuracy": 0.0})
        v1_1_c = v1_1_results["category_performance"].get(cat, {"passed": 0, "total": 0, "accuracy": 0.0})
        delta = round(v1_1_c["accuracy"] - v1_c["accuracy"], 2)
        category_comparison[cat] = {
            "v1": v1_c,
            "v1_1": v1_1_c,
            "accuracy_delta": delta,
            "improved": delta > 0,
        }

    language_comparison = {}
    for lang in all_languages:
        v1_l = v1_results["language_performance"].get(lang, {"passed": 0, "total": 0, "accuracy": 0.0})
        v1_1_l = v1_1_results["language_performance"].get(lang, {"passed": 0, "total": 0, "accuracy": 0.0})
        delta = round(v1_1_l["accuracy"] - v1_l["accuracy"], 2)
        language_comparison[lang] = {
            "v1": v1_l,
            "v1_1": v1_1_l,
            "accuracy_delta": delta,
            "improved": delta > 0,
        }

    overall_delta = round(v1_1_results["accuracy"] - v1_results["accuracy"], 4)

    comparison_report = {
        "evaluation_target": "NairaLLM Generalization on 55 Unseen Tests",
        "date": "2026-08-15",
        "models": {
            "v1": {
                "checkpoint": str(v1_ckpt),
                "dataset_size": 16,
                "passed": v1_results["passed_tests"],
                "total": v1_results["total_unseen_tests"],
                "accuracy": v1_results["accuracy"],
                "failures": v1_results["failure_taxonomy_distribution"],
            },
            "v1_1": {
                "checkpoint": str(v1_1_ckpt),
                "dataset_size": 517,
                "passed": v1_1_results["passed_tests"],
                "total": v1_1_results["total_unseen_tests"],
                "accuracy": v1_1_results["accuracy"],
                "failures": v1_1_results["failure_taxonomy_distribution"],
            },
        },
        "overall_improvement_delta": overall_delta,
        "category_comparison": category_comparison,
        "language_comparison": language_comparison,
        "detailed_case_comparison": [
            {
                "test_id": UNSEEN_TEST_CASES[i].test_id,
                "prompt": UNSEEN_TEST_CASES[i].user_prompt,
                "category": UNSEEN_TEST_CASES[i].category,
                "language": UNSEEN_TEST_CASES[i].language,
                "v1_passed": v1_results["records"][i]["passed"],
                "v1_tool": v1_results["records"][i]["extracted_tool"],
                "v1_1_passed": v1_1_results["records"][i]["passed"],
                "v1_1_tool": v1_1_results["records"][i]["extracted_tool"],
            }
            for i in range(len(UNSEEN_TEST_CASES))
        ],
    }

    report_file = Path("NairaLLM/evaluation/results/v1_vs_v1_1_report.json")
    report_file.parent.mkdir(parents=True, exist_ok=True)
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(comparison_report, f, indent=2, ensure_ascii=False)

    print("\n--------------------------------------------------")
    print(f"Overall Accuracy Delta: {'+' if overall_delta >= 0 else ''}{round(overall_delta * 100, 1)} percentage points")
    print(f"Report saved to {report_file}")
    print("==================================================")

    return comparison_report


def main() -> None:
    asyncio.run(run_comparison())


if __name__ == "__main__":
    main()
