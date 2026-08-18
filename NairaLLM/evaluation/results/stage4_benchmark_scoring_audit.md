# NairaLLM Final V1 — Stage 4 Benchmark Scoring Failure Audit

- **Audit Date**: `2026-08-18 02:25:00 UTC`
- **Target Suite**: `NairaLLM/evaluation/suites/final_v1_benchmark_suite.py`
- **Target Evaluation**: Stage 4 Tools Post-Training Validation (`nairallm_v1_tools_checkpoint.pt`)
- **Previously Reported Accuracy**: `237 / 360 = 65.83%`
- **Formal Status**: **`INVALID_SCORING_IMPLEMENTATION`**
- **Action**: **STOP STAGE 5. REBUILD BENCHMARK ENGINE V2.**

---

## 1. Executive Summary

An audit of the evaluation suite `final_v1_benchmark_suite.py` revealed that the reported benchmark score of **65.83% (237/360)** is unsound. The evaluation suite contained severe architectural flaws in its scoring predicates, which allowed arbitrary gibberish, broken tokens, and malformed fragments to receive `Passed: True` ratings across 11 of 18 sections.

Specifically:
- **220 out of 237 reported passes** (92.8% of all passing cases) passed solely due to trivial length fallbacks (`len > 5` or `len > 0`).
- Ordinary factual and language prompts (such as *"explain operating system kernel"*, *"RAM vs ROM"*, *"virtual memory"*, *"Unix architecture"*) that generated meaningless token soup (e.g. ` saa adjns Pythoncation Nati attempted've sing`) were marked as 100% successful.
- In tool sections, no JSON syntax validation, argument key extraction, or type verification was performed in `7_tool_arguments`.
- In multiple sections, a boolean condition `(not expected_intent)` short-circuited all logic whenever `expected_intent` was not explicitly specified.

As a consequence, the Stage 4 benchmark score of 65.83% has been **voided and marked `INVALID_SCORING_IMPLEMENTATION`**.

---

## 2. Line-by-Line Code Audit of `final_v1_benchmark_suite.py`

### Flaw 1: Trivial Length Fallback (`len > 5`)
**Lines 211–213**:
```python
elif section in ["1_language", "2_context", "3_reasoning", "4_planning", "5_intent", "16_multilingual", "18_notool_decisions"]:
    # Passing requires coherent response and matching intent if specified
    passed = intent_match or len(generated_response.strip()) > 5
```
- **Impact**: Any text generation with length > 5 was counted as a pass. Because untrained, under-trained, or corrupted models still emit more than 5 characters of random tokens, this gave an artificial **100% score (140/140 passes)** across 7 core cognitive sections.

### Flaw 2: Non-Empty String Fallback (`len > 0`)
**Lines 216–217**:
```python
elif section in ["11_verification", "12_recovery", "14_proactive_behavior", "15_user_state_emotion"]:
    passed = len(generated_response.strip()) > 0
```
- **Impact**: Emitting a single non-whitespace character counted as a full pass. This gave an artificial **100% score (80/80 passes)** across 4 sections.

### Flaw 3: Intent Short-Circuit Bug (`not expected_intent`)
**Lines 214–215**:
```python
elif section in ["8_memory", "9_browser", "10_coding", "17_multistep_tasks"]:
    passed = tool_selection_correct or (not expected_intent or intent_match)
```
- **Impact**: When `expected_intent` was not defined or was `None`, `(not expected_intent)` evaluated to `True`. The entire expression evaluated to `True` without checking `tool_selection_correct` or any semantic criteria.

### Flaw 4: Zero Argument & Schema Verification in Tool Arguments Section
**Lines 207–208**:
```python
if section in ["6_tool_selection", "7_tool_arguments"]:
    passed = tool_selection_correct
```
- **Impact**: Section `7_tool_arguments` (which specifically tests JSON argument correctness, required fields, and parameter types) never executed any argument verification code. It merely checked `tool_selection_correct`, which was defined in lines 184–188 as substring presence of `<|tool_call|>` and the tool name.

### Flaw 5: Substring-Only Tool Call Detection
**Lines 184–188**:
```python
if requires_tool:
    if expected_tool:
        tool_selection_correct = has_tool_call and (expected_tool in generated_response)
```
- **Impact**: If the model output `<|tool_call|>\n{"name": "__s. ... garbage ...` or `<|tool_call|> pc_system_settings`, this counted as a valid tool invocation without requiring valid JSON arguments or valid tool contracts.

### Flaw 6: Hardware Attribution & Default CPU Runtime
**Lines 136, 315**:
```python
self.runtime = NairaRuntime(checkpoint_path=self.resolved_checkpoint_path)
...
"device": getattr(self.runtime, "device", "cpu")
```
- **Impact**: `NairaRuntime` initialized with `device="cpu"` by default. The benchmark runner did not detect `torch.cuda.is_available()`, causing GPU-enabled execution environments (such as Tesla T4 in Google Colab) to execute inference on CPU or misreport execution device.

---

## 3. Mathematical Breakdown of False Passes

| Section | Evaluated Prompts | Reported Passed | True Passes | False Positive Passes | Scoring Bug |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `1_language` | 20 | 20 | 0 | 20 | `len > 5` fallback |
| `2_context` | 20 | 20 | 0 | 20 | `len > 5` fallback |
| `3_reasoning` | 20 | 20 | 0 | 20 | `len > 5` fallback |
| `4_planning` | 20 | 20 | 0 | 20 | `len > 5` fallback |
| `5_intent` | 20 | 20 | 0 | 20 | `len > 5` fallback |
| `6_tool_selection` | 20 | 5 | 0–2 | ~3–5 | Substring matching without AST |
| `7_tool_arguments` | 20 | 0 | 0 | 0 | Unimplemented schema check |
| `8_memory` | 20 | 6 | 0 | 6 | `not expected_intent` short-circuit |
| `9_browser` | 20 | 0 | 0 | 0 | Short-circuit logic |
| `10_coding` | 20 | 3 | 0 | 3 | `not expected_intent` short-circuit |
| `11_verification` | 20 | 20 | 0 | 20 | `len > 0` fallback |
| `12_recovery` | 20 | 20 | 0 | 20 | `len > 0` fallback |
| `13_safety` | 20 | 0 | 0 | 0 | Keyword search |
| `14_proactive_behavior` | 20 | 20 | 0 | 20 | `len > 0` fallback |
| `15_user_state_emotion` | 20 | 20 | 0 | 20 | `len > 0` fallback |
| `16_multilingual` | 20 | 20 | 0 | 20 | `len > 5` fallback |
| `17_multistep_tasks` | 20 | 0 | 0 | 0 | Short-circuit logic |
| `18_notool_decisions` | 20 | 20 | 0 | 20 | `len > 5` fallback |
| **TOTAL** | **360** | **237 (65.83%)** | **~0–2 (<1%)** | **~235** | **Systemic Scorer Failure** |

---

## 4. Invalidation Mandate & Next Steps

1. **Stage 5 Behavior & Safety Training**: **STOPPED**. No Stage 5 training will begin until Stage 4 has been honestly measured under strict Benchmark V2.
2. **Benchmark Engine V2**: A new deterministic, strict, AST-based, and rubric-driven evaluator (`final_v1_benchmark_v2.py`) is implemented.
3. **Provenance Integrity**: Auto-detects CUDA / CPU hardware and requires valid schema and semantic satisfaction before marking any test as passed.
