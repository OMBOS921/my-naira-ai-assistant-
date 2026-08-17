"""
Semantic Pretraining Corpus Generator for NairaLLM V1.5 (Dataset A Expansion).

Generates a high-quality, provenance-tracked, multi-lingual, multi-domain text corpus
for foundational language pretraining (100,000–150,000 verified tokens):
- English natural language (reasoning, logic, rhetoric, epistemology)
- Hindi / Devanagari (grammar, linguistics, computer science, mathematics, science)
- Hinglish (authentic developer discourse, backend engineering, cloud DevOps)
- Technical systems (Operating Systems, Computer Architecture, Networks, Databases)
- Algorithms, data structures, and computational complexity
- Programming paradigms, compiler internals, and multi-language code snippets
- Software engineering, design patterns, and distributed systems
- APIs, HTTP protocols, web development, and browser rendering
- Cybersecurity, cryptography, and application security
- Linux system administration, CLI utilities, and kernel primitives
- Technical documentation, ADRs, post-mortems, and runbooks
- Structured JSON schemas, payloads, and telemetry manifests
- Error diagnostics, compiler outputs, and structured logs
- Naira OS architectural foundations and bounded autonomy

All samples comply with strict provenance rules (zero closed proprietary distillation).
Outputs to: dataset/semantic_corpus/semantic_pretrain_v1_5_expanded.jsonl
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any

# Ensure workspace root in sys.path
workspace_root = Path(__file__).resolve().parent.parent.parent
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from NairaLLM.dataset.generators.algorithms_complexity_gen import get_algorithms_complexity_samples
from NairaLLM.dataset.generators.algorithms_expanded_gen import get_algorithms_expanded_samples
from NairaLLM.dataset.generators.apis_web_gen import get_apis_web_samples
from NairaLLM.dataset.generators.applied_engineering_gen import get_applied_engineering_samples
from NairaLLM.dataset.generators.architecture_hardware_gen import get_architecture_hardware_samples
from NairaLLM.dataset.generators.code_advanced_gen import get_code_advanced_samples
from NairaLLM.dataset.generators.code_expanded_gen import get_code_expanded_samples
from NairaLLM.dataset.generators.code_multilang_gen import get_code_multilang_samples
from NairaLLM.dataset.generators.computational_linguistics_gen import get_computational_linguistics_samples
from NairaLLM.dataset.generators.core_reasoning_gen import get_core_reasoning_samples
from NairaLLM.dataset.generators.data_structures_gen import get_data_structures_samples
from NairaLLM.dataset.generators.databases_storage_gen import get_databases_storage_samples
from NairaLLM.dataset.generators.diagnostics_errors_gen import get_diagnostics_errors_samples
from NairaLLM.dataset.generators.documentation_gen import get_documentation_samples
from NairaLLM.dataset.generators.domain_deep_dives_gen import get_domain_deep_dives_samples
from NairaLLM.dataset.generators.hindi_advanced_gen import get_hindi_advanced_samples
from NairaLLM.dataset.generators.hindi_expanded_gen import get_hindi_expanded_samples
from NairaLLM.dataset.generators.hindi_linguistics_gen import get_hindi_linguistics_samples
from NairaLLM.dataset.generators.hinglish_advanced_gen import get_hinglish_advanced_samples
from NairaLLM.dataset.generators.hinglish_discourse_gen import get_hinglish_discourse_samples
from NairaLLM.dataset.generators.hinglish_expanded_gen import get_hinglish_expanded_samples
from NairaLLM.dataset.generators.indic_corpus_gen import get_indic_corpus_samples
from NairaLLM.dataset.generators.linux_cli_gen import get_linux_cli_samples
from NairaLLM.dataset.generators.multilingual_technical_gen import get_multilingual_technical_samples
from NairaLLM.dataset.generators.naira_architecture_gen import get_naira_architecture_samples
from NairaLLM.dataset.generators.natural_language_gen import get_natural_language_samples
from NairaLLM.dataset.generators.networking_dist_gen import get_networking_dist_samples
from NairaLLM.dataset.generators.programming_paradigms_gen import get_programming_paradigms_samples
from NairaLLM.dataset.generators.science_math_gen import get_science_math_samples
from NairaLLM.dataset.generators.security_crypto_gen import get_security_crypto_samples
from NairaLLM.dataset.generators.software_engineering_gen import get_software_engineering_samples
from NairaLLM.dataset.generators.structured_data_gen import get_structured_data_samples
from NairaLLM.dataset.generators.structured_expanded_gen import get_structured_expanded_samples
from NairaLLM.dataset.generators.systems_expanded_gen import get_systems_expanded_samples
from NairaLLM.dataset.generators.systems_os_gen import get_systems_os_samples
from NairaLLM.dataset.generators.technical_encyclopedia_gen import get_technical_encyclopedia_samples
from NairaLLM.dataset.generators.technical_explanations_gen import get_technical_explanations_samples
from NairaLLM.dataset.generators.world_knowledge_gen import get_world_knowledge_samples
from NairaLLM.model.tokenizer.naira_tokenizer import NairaTokenizer


def load_seed_records() -> list[dict[str, Any]]:
    """Loads the pristine 27 seed records from semantic_pretrain_v1_5.jsonl."""
    seed_path = workspace_root / "NairaLLM" / "dataset" / "semantic_corpus" / "semantic_pretrain_v1_5.jsonl"
    if not seed_path.exists():
        return []
    records = []
    with open(seed_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def build_expanded_corpus() -> list[dict[str, Any]]:
    """Gathers all seed and modular generator records, validates hygiene, and returns unique samples."""
    generators = [
        get_natural_language_samples,
        get_hindi_linguistics_samples,
        get_hindi_expanded_samples,
        get_hindi_advanced_samples,
        get_hinglish_discourse_samples,
        get_hinglish_expanded_samples,
        get_hinglish_advanced_samples,
        get_systems_os_samples,
        get_systems_expanded_samples,
        get_architecture_hardware_samples,
        get_networking_dist_samples,
        get_databases_storage_samples,
        get_algorithms_complexity_samples,
        get_algorithms_expanded_samples,
        get_data_structures_samples,
        get_programming_paradigms_samples,
        get_software_engineering_samples,
        get_apis_web_samples,
        get_security_crypto_samples,
        get_linux_cli_samples,
        get_documentation_samples,
        get_technical_explanations_samples,
        get_structured_data_samples,
        get_structured_expanded_samples,
        get_diagnostics_errors_samples,
        get_code_multilang_samples,
        get_code_expanded_samples,
        get_code_advanced_samples,
        get_science_math_samples,
        get_world_knowledge_samples,
        get_technical_encyclopedia_samples,
        get_indic_corpus_samples,
        get_applied_engineering_samples,
        get_multilingual_technical_samples,
        get_computational_linguistics_samples,
        get_core_reasoning_samples,
        get_domain_deep_dives_samples,
        get_naira_architecture_samples,
    ]

    all_records = load_seed_records()
    for g in generators:
        all_records.extend(g())

    # Quality and Validation Loop
    seen_ids = set()
    validated_samples: list[dict[str, Any]] = []

    dataset_b_forbidden_markers = [
        "<|tool_call|>",
        "<|tool_result|>",
        "<|user|>",
        "<|assistant|>",
        "<|thought|>",
        "<|plan|>",
        "<|verify|>",
    ]

    for r in all_records:
        rec_id = r.get("id", "unknown")
        if rec_id in seen_ids:
            continue
        seen_ids.add(rec_id)

        text = r.get("text", "").strip()
        if not text:
            raise ValueError(f"Empty text in record: {rec_id}")

        # Check for Dataset B leakage
        for marker in dataset_b_forbidden_markers:
            if marker in text:
                raise ValueError(f"Forbidden Dataset B token '{marker}' detected in Dataset A record {rec_id}!")

        # Validate JSON for structured data
        if r.get("domain") == "structured_data":
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Malformed JSON in record {rec_id}: {exc}") from exc

        # Validate Python AST for code records with python fences
        if "```python" in text:
            code_snippet = text.split("```python")[1].split("```")[0].strip()
            try:
                ast.parse(code_snippet)
            except SyntaxError as exc:
                raise ValueError(f"Python syntax error in record {rec_id}: {exc}") from exc

        # Ensure complete provenance
        prov = r.get("provenance", {})
        if not prov.get("license") or not prov.get("author") or not prov.get("acquisition_method"):
            raise ValueError(f"Incomplete provenance in record {rec_id}")

        validated_samples.append(r)

    return validated_samples


def main() -> None:
    samples = build_expanded_corpus()
    out_dir = workspace_root / "NairaLLM" / "dataset" / "semantic_corpus"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "semantic_pretrain_v1_5_expanded.jsonl"

    with open(out_file, "w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    tok_path = workspace_root / "NairaLLM" / "model" / "tokenizer" / "naira_tokenizer.json"
    tokenizer = NairaTokenizer(tok_path)

    total_tokens = sum(len(tokenizer.encode(s["text"])) for s in samples)
    total_chars = sum(len(s["text"]) for s in samples)
    file_bytes = out_file.stat().st_size
    file_kb = round(file_bytes / 1024, 2)
    file_mb = round(file_bytes / (1024 * 1024), 4)

    print("==================================================")
    print("   NAIRALLM V1.5 — DATASET A EXPANSION COMPLETE   ")
    print("==================================================")
    print(f"Total Unique Records:      {len(samples)}")
    print(f"Total Characters:          {total_chars:,} ({file_kb} KB / {file_mb} MB)")
    print(f"Total Verified Tokens:     {total_tokens:,}")
    print(f"Average Tokens / Record:   {round(total_tokens / len(samples), 2)}")
    print(f"Saved To:                  {out_file}")
    print("==================================================")


if __name__ == "__main__":
    main()
