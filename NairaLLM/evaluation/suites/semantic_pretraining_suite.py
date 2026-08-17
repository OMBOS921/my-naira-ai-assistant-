"""
Semantic Language Foundation Evaluation Benchmark for NairaLLM V1.5.

Measures foundational language representation and general semantic coherence across:
1. English language comprehension & continuation
2. Hindi / Devanagari text comprehension
3. Hinglish bilingual discourse
4. Contextual completion
5. Operating systems & technical concept completion
6. Code syntax & algorithm completion
7. Structured JSON format integrity

Evaluates both NumPy (.npz) and PyTorch (.pt) checkpoints and runtime models.
"""

from __future__ import annotations

import json
import logging
import math
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

# Ensure workspace root in sys.path
workspace_root = Path(__file__).resolve().parent.parent.parent.parent
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from NairaLLM.model.config.model_config import NairaModelConfig
from NairaLLM.model.runtime.naira_runtime import NairaRuntime
from NairaLLM.model.tokenizer.naira_tokenizer import NairaTokenizer

_LOG = logging.getLogger("nairallm.semantic_eval")


@dataclass
class SemanticTestCase:
    test_id: str
    prompt: str
    language: str  # "en", "hi", "hinglish"
    category: str  # "english_comprehension", "hindi_comprehension", "hinglish_comprehension", "contextual_completion", "technical_text", "code_completion", "json_structured"
    expected_keywords: list[str]
    description: str


SEMANTIC_BENCHMARK_CASES: list[SemanticTestCase] = [
    # 1. English Comprehension & Continuation
    SemanticTestCase(
        test_id="SEM_EN_01",
        prompt="Effective communication in software engineering teams requires",
        language="en",
        category="english_comprehension",
        expected_keywords=["clarity", "listening", "structure", "examples", "team", "code", "understanding", "documentation"],
        description="English software team communication continuation",
    ),
    SemanticTestCase(
        test_id="SEM_EN_02",
        prompt="Language models process text by transforming discrete tokens into",
        language="en",
        category="english_comprehension",
        expected_keywords=["vector", "embedding", "dense", "representation", "attention", "layers", "space"],
        description="Transformer embeddings foundational definition",
    ),

    # 2. Hindi Devanagari Comprehension
    SemanticTestCase(
        test_id="SEM_HI_01",
        prompt="ऑपरेटिंग सिस्टम का मुख्य कार्य कंप्यूटर हार्डवेयर और",
        language="hi",
        category="hindi_comprehension",
        expected_keywords=["उपयोगकर्ता", "अनुप्रयोगों", "मेमोरी", "प्रक्रिया", "सॉफ्टवेयर", "माध्यम", "नियंत्रण"],
        description="Hindi operating system core functionality definition",
    ),
    SemanticTestCase(
        test_id="SEM_HI_02",
        prompt="सुरक्षा और गोपनीयता डिजिटल दुनिया में सबसे",
        language="hi",
        category="hindi_comprehension",
        expected_keywords=["महत्वपूर्ण", "पासवर्ड", "सुरक्षित", "डेटा", "नियमों", "आवश्यक", "पहलुओं"],
        description="Hindi security and data privacy continuation",
    ),

    # 3. Hinglish Bilingual Discourse
    SemanticTestCase(
        test_id="SEM_HING_01",
        prompt="Clean architecture maintain karne se codebase",
        language="hinglish",
        category="hinglish_comprehension",
        expected_keywords=["maintainable", "simple", "modular", "easy", "tests", "features", "scalable", "clean"],
        description="Hinglish clean architecture continuation",
    ),
    SemanticTestCase(
        test_id="SEM_HING_02",
        prompt="FastAPI me async route handlers likhte time",
        language="hinglish",
        category="hinglish_comprehension",
        expected_keywords=["blocking", "async", "event loop", "non-blocking", "concurrency", "await", "io"],
        description="Hinglish async backend event loop continuation",
    ),

    # 4. Contextual Completion
    SemanticTestCase(
        test_id="SEM_CTX_01",
        prompt="When optimizing low-latency applications, profiling memory allocation helps",
        language="en",
        category="contextual_completion",
        expected_keywords=["identify", "bottleneck", "gc", "garbage", "overhead", "latency", "reduce", "performance"],
        description="Contextual memory profiling continuation",
    ),
    SemanticTestCase(
        test_id="SEM_CTX_02",
        prompt="A robust distributed system handles transient network failures by using",
        language="en",
        category="contextual_completion",
        expected_keywords=["retry", "exponential", "backoff", "circuit", "breaker", "jitter", "fallback"],
        description="Contextual resilient distributed systems continuation",
    ),

    # 5. Technical Text & Systems Concepts
    SemanticTestCase(
        test_id="SEM_TECH_01",
        prompt="In modern operating systems, virtual memory abstracts physical RAM using",
        language="en",
        category="technical_text",
        expected_keywords=["page", "mmu", "tables", "address", "fault", "space", "translation", "frames"],
        description="Virtual memory paging and MMU continuation",
    ),
    SemanticTestCase(
        test_id="SEM_TECH_02",
        prompt="Inter-process communication mechanisms include Unix domain sockets and",
        language="en",
        category="technical_text",
        expected_keywords=["shared memory", "pipes", "messages", "queues", "posix", "signals", "semaphores"],
        description="IPC mechanisms and memory channels continuation",
    ),

    # 6. Code Completion & Algorithms
    SemanticTestCase(
        test_id="SEM_CODE_01",
        prompt="def binary_search(arr: list[int], target: int) -> int:\n    low, high = 0, len(arr) - 1\n    while",
        language="en",
        category="code_completion",
        expected_keywords=["low <= high", "mid", "target", "return", "low", "high"],
        description="Binary search while-loop condition continuation",
    ),
    SemanticTestCase(
        test_id="SEM_CODE_02",
        prompt="from dataclasses import dataclass\n@dataclass\nclass ToolResult:\n    tool_name: str\n    status: str\n   ",
        language="en",
        category="code_completion",
        expected_keywords=["output", "metadata", "time", "int", "str", "latency", "data", "result"],
        description="Dataclass field schema continuation",
    ),

    # 7. Structured JSON Syntax
    SemanticTestCase(
        test_id="SEM_JSON_01",
        prompt="{\n  \"action\": \"system_diagnostic\",\n  \"parameters\": {",
        language="en",
        category="json_structured",
        expected_keywords=["\"", ":", "}", "format", "target", "include", "verbose", "true"],
        description="JSON structured parameters object completion",
    ),
    SemanticTestCase(
        test_id="SEM_JSON_02",
        prompt="{\n  \"model\": \"nairallm_v1_5\",\n  \"status\": \"ready\",\n  \"metrics\": [",
        language="en",
        category="json_structured",
        expected_keywords=["{", "}", "]", "\"", "name", "loss", "perplexity"],
        description="JSON array and nested object continuation",
    ),
]


@dataclass
class SemanticEvalRecord:
    test_id: str
    prompt: str
    language: str
    category: str
    generated_text: str
    matched_keywords: list[str]
    coherence_passed: bool
    latency_ms: float


class SemanticPretrainingSuite:
    """Evaluates foundational language representations across 7 domains."""

    def __init__(
        self,
        runtime: NairaRuntime | None = None,
        checkpoint_path: str | Path | None = None,
    ) -> None:
        if runtime is not None:
            self.runtime = runtime
        else:
            tok_path = workspace_root / "NairaLLM" / "model" / "tokenizer" / "naira_tokenizer.json"
            tok = NairaTokenizer(tok_path)
            if checkpoint_path is not None and Path(checkpoint_path).exists():
                self.runtime = NairaRuntime(tokenizer=tok, checkpoint_path=checkpoint_path)
            else:
                default_npz = workspace_root / "NairaLLM" / "training" / "checkpoints" / "numpy_model.npz"
                default_pt = workspace_root / "NairaLLM" / "training" / "checkpoints" / "naira_model_v1_5_pilot_latest.pt"
                chosen_ckpt = default_pt if default_pt.exists() else (default_npz if default_npz.exists() else None)
                self.runtime = NairaRuntime(tokenizer=tok, checkpoint_path=chosen_ckpt)

    def evaluate_test_case(self, case: SemanticTestCase) -> SemanticEvalRecord:
        t0 = time.perf_counter()
        gen_text = self.runtime.generate(
            prompt=case.prompt,
            max_new_tokens=32,
            temperature=0.0,
        )
        dt = (time.perf_counter() - t0) * 1000.0

        # Isolate ONLY newly generated continuation text
        continuation = gen_text[len(case.prompt):].strip().lower()
        prompt_lower = case.prompt.lower()
        
        # Clean expected keywords to exclude any keywords present in the input prompt
        clean_expected = [kw for kw in case.expected_keywords if kw.lower() not in prompt_lower]
        if not clean_expected:
            clean_expected = case.expected_keywords

        matched = [kw for kw in clean_expected if kw.lower() in continuation]
        passed = (len(matched) >= 1) and len(continuation) > 2

        return SemanticEvalRecord(
            test_id=case.test_id,
            prompt=case.prompt,
            language=case.language,
            category=case.category,
            generated_text=gen_text,
            matched_keywords=matched,
            coherence_passed=passed,
            latency_ms=round(dt, 2),
        )

    def run_suite(self, output_dir: Path | None = None) -> dict[str, Any]:
        records = [self.evaluate_test_case(c) for c in SEMANTIC_BENCHMARK_CASES]
        total = len(records)
        passed_cnt = sum(1 for r in records if r.coherence_passed)
        accuracy = round(passed_cnt / total, 4)

        # Categorize by language and category
        lang_stats: dict[str, dict[str, int]] = {}
        category_stats: dict[str, dict[str, int]] = {}

        for r in records:
            lang_stats.setdefault(r.language, {"total": 0, "passed": 0})
            lang_stats[r.language]["total"] += 1
            if r.coherence_passed:
                lang_stats[r.language]["passed"] += 1

            category_stats.setdefault(r.category, {"total": 0, "passed": 0})
            category_stats[r.category]["total"] += 1
            if r.coherence_passed:
                category_stats[r.category]["passed"] += 1

        summary = {
            "total_tests": total,
            "passed_tests": passed_cnt,
            "accuracy": accuracy,
            "language_breakdown": {
                k: {"passed": v["passed"], "total": v["total"], "accuracy": round(v["passed"] / v["total"], 2)}
                for k, v in lang_stats.items()
            },
            "category_breakdown": {
                k: {"passed": v["passed"], "total": v["total"], "accuracy": round(v["passed"] / v["total"], 2)}
                for k, v in category_stats.items()
            },
            "domain_breakdown": {
                k: {"passed": v["passed"], "total": v["total"], "accuracy": round(v["passed"] / v["total"], 2)}
                for k, v in category_stats.items()
            },
            "records": [asdict(r) for r in records],
        }

        # Save report
        out_dir = output_dir or (workspace_root / "NairaLLM" / "evaluation" / "results")
        out_dir.mkdir(parents=True, exist_ok=True)
        report_file = out_dir / "v1_5_semantic_report.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        return summary


def main() -> None:
    suite = SemanticPretrainingSuite()
    print("==================================================")
    print("     NAIRALLM V1.5 SEMANTIC PRETRAINING SUITE     ")
    print("==================================================")
    res = suite.run_suite()
    print(f"Passed: {res['passed_tests']} / {res['total_tests']} ({res['accuracy']*100:.1f}%)")

    print("\nLanguage Breakdown:")
    for l, stats in res["language_breakdown"].items():
        print(f"  - {l:12s}: {stats['passed']}/{stats['total']} ({stats['accuracy']*100:.1f}%)")

    print("\nCategory Breakdown (7 Semantic Dimensions):")
    for c, stats in res["category_breakdown"].items():
        print(f"  - {c:24s}: {stats['passed']}/{stats['total']} ({stats['accuracy']*100:.1f}%)")


if __name__ == "__main__":
    main()
