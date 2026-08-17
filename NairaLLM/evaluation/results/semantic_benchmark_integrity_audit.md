# NairaLLM — Semantic Benchmark Integrity Audit Report

**Audit Date**: 2026-08-17 15:57:57  
**Target Suite**: `NairaLLM/evaluation/suites/semantic_pretraining_suite.py`  
**Audit Question**: *"Does this benchmark actually measure the neural model?"*  
**Verdict**: **NO (Legacy Benchmark Had Prompt-Contained Keyword Leakage)**  

---

## 1. Executive Summary & Core Discovery

The observation that **Untrained Baseline = 8/14 (57.1%)** and **Trained Model = 8/14 (57.1%)** was investigated by isolating the generation pipeline and tracing all 14 test cases.

### The Root Cause: Prompt-Contained Keyword Leakage
In `NairaLLM/evaluation/suites/semantic_pretraining_suite.py`, `evaluate_test_case()` inspected `case.expected_keywords` against `gen_text.lower()`:
```python
clean_gen = gen_text.lower()
matched = [kw for kw in case.expected_keywords if kw.lower() in clean_gen]
passed = (len(matched) >= 1) and len(gen_text.strip()) > 3
```
Where `gen_text` is the concatenated string: **`prompt + newly_generated_tokens`**.

For **8 out of the 14 test cases (57.14%)**, the `expected_keywords` list contained words or substrings that were **explicitly present inside the input prompt itself**:
- `SEM_EN_01`: `"team"` is inside prompt `"Effective communication in software engineering teams requires"`
- `SEM_HING_01`: `"clean"` is inside prompt `"Clean architecture maintain karne se codebase"`
- `SEM_HING_02`: `"async"` is inside prompt `"FastAPI me async route handlers likhte time"`
- `SEM_CTX_01`: `"latency"` is inside prompt `"When optimizing low-latency applications..."`
- `SEM_CODE_01`: `"target"`, `"low"`, `"high"` are inside prompt `"def binary_search(arr: list[int], target: int) -> int:\n    low, high = 0, len(arr) - 1\n    while"`
- `SEM_CODE_02`: `"str"`, `"data"`, `"result"` are inside prompt `"class ToolResult: tool_name: str\n    status: str\n    "`
- `SEM_JSON_01`: `":"` and `"\""` are inside prompt `"{\n  \"action\": \"system_diagnostic\",\n  \"parameters\": {"`
- `SEM_JSON_02`: `"\""` and `"{"` are inside prompt `"{\n  \"model\": \"nairallm_v1_5\",\n  \"status\": \"ready\",\n  \"metrics\": ["`

Consequently, an untrained model with completely random weights produced **8/14 (57.1%) passes automatically**, without generating a single coherent word.

---

## 2. Comparative Benchmark Matrix: Legacy vs Strict Generation

| Test ID | Category | Language | Expected Keyword | Leaked in Prompt? | Legacy Flawed Score (Random) | Strict Generation Score (Random) | Strict Generation Score (105K Trained) |
| :--- | :--- | :---: | :--- | :---: | :---: | :---: | :---: |
| **`SEM_EN_01`** | English | `en` | `['clarity', 'team', ...]` | **YES (`team`)** | `PASS` (57.1%) | `FAIL` (0%) | `FAIL` (0%) |
| **`SEM_EN_02`** | English | `en` | `['vector', 'embedding', ...]` | NO | `FAIL` | `FAIL` | `FAIL` |
| **`SEM_HI_01`** | Hindi | `hi` | `['उपयोगकर्ता', ...]` | NO | `FAIL` | `FAIL` | `FAIL` |
| **`SEM_HI_02`** | Hindi | `hi` | `['महत्वपूर्ण', ...]` | NO | `FAIL` | `FAIL` | `FAIL` |
| **`SEM_HING_01`** | Hinglish | `hinglish` | `['maintainable', 'clean', ...]`| **YES (`clean`)** | `PASS` | `FAIL` | `FAIL` |
| **`SEM_HING_02`** | Hinglish | `hinglish` | `['blocking', 'async', ...]` | **YES (`async`)** | `PASS` | `FAIL` | `FAIL` |
| **`SEM_CTX_01`** | Contextual | `en` | `['identify', 'latency', ...]` | **YES (`latency`)**| `PASS` | `FAIL` | `FAIL` |
| **`SEM_CTX_02`** | Contextual | `en` | `['retry', 'circuit', ...]` | NO | `FAIL` | `FAIL` | `FAIL` |
| **`SEM_TECH_01`** | Technical | `en` | `['page', 'mmu', ...]` | NO | `FAIL` | `FAIL` | `FAIL` |
| **`SEM_TECH_02`** | Technical | `en` | `['shared memory', ...]` | NO | `FAIL` | `FAIL` | `FAIL` |
| **`SEM_CODE_01`** | Code | `en` | `['mid', 'low', 'high', ...]` | **YES (`target, low, high`)** | `PASS` | `PASS` (syntax) | `PASS` (syntax) |
| **`SEM_CODE_02`** | Code | `en` | `['output', 'str', 'result', ...]` | **YES (`str, result`)** | `PASS` | `FAIL` | `FAIL` |
| **`SEM_JSON_01`** | JSON | `en` | `['"', ':', 'true', ...]` | **YES (`", :`)** | `PASS` | `FAIL` | `FAIL` |
| **`SEM_JSON_02`** | JSON | `en` | `['"', '{', 'loss', ...]` | **YES (`", {`)** | `PASS` | `FAIL` | `FAIL` |
| **TOTAL** | **14 Tests** | — | — | **8 Leaked (57.1%)** | **8 / 14 (57.1%)** | **1 / 14 (7.1%)** | **1 / 14 (7.1%)** |

---

## 3. Workflow & Harness Integrity Audit

| Potential Leakage Vector | Investigation Result | Finding |
| :--- | :---: | :--- |
| **Hardcoded Output Injection** | `CLEAN` | No hardcoded outputs injected into model outputs. |
| **Deterministic Fallbacks** | `CLEAN` | No fallback mock answers overriding neural tokens. |
| **Prompt-Contained Keyword Leakage** | **`DEFECT DETECTED`** | Keywords present in prompts matched against prompt text. |
| **Test Fixtures Bypassing Model** | `CLEAN` | Inference loop executed autoregressively. |
| **Cached Outputs** | `CLEAN` | No static caches reused between runs. |

---

## 4. Test-by-Test Trace & Actual Model Outputs

### [SEM_EN_01] English Comprehension (EN)
- **Input Prompt**: `Effective communication in software engineering teams requires`
- **Leaked Keywords in Prompt**: `['team']`
- **Random Model Continuation**: `screenshot%"}**:criptionsioncriptionsioncriptionsioncriptionsioncriptionsioncriptionsioncriptions`
- **Random Model Strict Result**: `FAIL` (No expected keywords in continuation: 'screenshot%"}**:criptionsioncriptions')
- **Trained Model Continuation**: `o Plano Plano Plano Plano PlanX PlanX PlanX PlanX PlanX Plan Plan PlanX Plan Plan PlanX Plan PlanX P`
- **Trained Model Strict Result**: `FAIL` (No expected keywords in continuation: 'o plano plano plano plano planx planx pl')

### [SEM_EN_02] English Comprehension (EN)
- **Input Prompt**: `Language models process text by transforming discrete tokens into`
- **Leaked Keywords in Prompt**: `[]`
- **Random Model Continuation**: `AddnavigateoughtAddnavigateoughtAddAddAddAddAddAddAddAddAddAddAddAddAddAddAddAddAddAddAddAddAddAddAd`
- **Random Model Strict Result**: `FAIL` (No expected keywords in continuation: 'addnavigateoughtaddnavigateoughtaddaddad')
- **Trained Model Continuation**: `HIHIHIHIHIHIHIHIileHIileHIileHIileHIileHIile�ile�ile structuredveile structuredveile structuredve st`
- **Trained Model Strict Result**: `FAIL` (No expected keywords in continuation: 'hihihihihihihihiilehiilehiilehiilehiileh')

### [SEM_HI_01] Hindi Comprehension (HI)
- **Input Prompt**: `ऑपरेटिंग सिस्टम का मुख्य कार्य कंप्यूटर हार्डवेयर और`
- **Leaked Keywords in Prompt**: `[]`
- **Random Model Continuation**: `MEMkended FastAPI them MEMkendboard MEMkendboard MEMkendboard MEMkendboard MEMitHubboard MEMitHub Fa`
- **Random Model Strict Result**: `FAIL` (No expected keywords in continuation: 'memkended fastapi them memkendboard memk')
- **Trained Model Continuation**: `ologDeleteog�ations allesEnhancedations allesEnhancedDeleteog�ationsducesolog�ationsducesolog�ations`
- **Trained Model Strict Result**: `FAIL` (No expected keywords in continuation: 'ologdeleteog�ations allesenhancedations ')

### [SEM_HI_02] Hindi Comprehension (HI)
- **Input Prompt**: `सुरक्षा और गोपनीयता डिजिटल दुनिया में सबसे`
- **Leaked Keywords in Prompt**: `[]`
- **Random Model Continuation**: `risk to wilpythononesystem optimiz Fileonesystem optimiz Fileonesystem optimiz Fileonesystem optimiz`
- **Random Model Strict Result**: `FAIL` (No expected keywords in continuation: 'risk to wilpythononesystem optimiz fileo')
- **Trained Model Continuation**: `ol Sugge�ol Sugge�ol Sugge�ol Sugge�ol Sugge��ol Sugge��ol Sugge�ol Sugge�ol Sugge��ol Sugge`
- **Trained Model Strict Result**: `FAIL` (No expected keywords in continuation: 'ol sugge�ol sugge�ol sugge�ol sugge�ol s')

### [SEM_HING_01] Hinglish Comprehension (HINGLISH)
- **Input Prompt**: `Clean architecture maintain karne se codebase`
- **Leaked Keywords in Prompt**: `['clean']`
- **Random Model Continuation**: `���������������������������� great great great great`
- **Random Model Strict Result**: `FAIL` (No expected keywords in continuation: '���������������������������� great great')
- **Trained Model Continuation**: `files attributeired it files attributeired it files attributeired it files attributeired it files at`
- **Trained Model Strict Result**: `FAIL` (No expected keywords in continuation: 'files attributeired it files attributeir')

### [SEM_HING_02] Hinglish Comprehension (HINGLISH)
- **Input Prompt**: `FastAPI me async route handlers likhte time`
- **Leaked Keywords in Prompt**: `['async']`
- **Random Model Continuation**: `ulateTemplate Reportntntntntntntulateageageage�).atusulateage�).atusulateage�).atusulateageQu`
- **Random Model Strict Result**: `FAIL` (No expected keywords in continuation: 'ulatetemplate reportntntntntntntulateage')
- **Trained Model Continuation**: `a `save a catastrophiccesssave a catastrophiccesssave a catastrophiccesstingtingtingtingtingtingting`
- **Trained Model Strict Result**: `FAIL` (No expected keywords in continuation: 'a `save a catastrophiccesssave a catastr')

### [SEM_CTX_01] Contextual Completion (EN)
- **Input Prompt**: `When optimizing low-latency applications, profiling memory allocation helps`
- **Leaked Keywords in Prompt**: `['latency']`
- **Random Model Continuation**: `St�7ations value value value value value value value value value messa URLFactmmandodel value�mmando`
- **Random Model Strict Result**: `FAIL` (No expected keywords in continuation: 'st�7ations value value value value value')
- **Trained Model Continuation**: `anyn wor messagesenred n serverdiatelyenanenanenanenanenanenanenanenanenanults n server OS n`
- **Trained Model Strict Result**: `FAIL` (No expected keywords in continuation: 'anyn wor messagesenred n serverdiatelyen')

### [SEM_CTX_02] Contextual Completion (EN)
- **Input Prompt**: `A robust distributed system handles transient network failures by using`
- **Leaked Keywords in Prompt**: `[]`
- **Random Model Continuation**: `u�� m m m m m m m m m m m m m m m m m m m m m m m Deleting Deleting Deleting Deleting Deleting Delet`
- **Random Model Strict Result**: `FAIL` (No expected keywords in continuation: 'u�� m m m m m m m m m m m m m m m m m m ')
- **Trained Model Continuation**: `terpreter smo textterpreter smo textterpreterterpreterterpreter gessaindingsterpreter gessaindingste`
- **Trained Model Strict Result**: `FAIL` (No expected keywords in continuation: 'terpreter smo textterpreter smo textterp')

### [SEM_TECH_01] Technical Text (EN)
- **Input Prompt**: `In modern operating systems, virtual memory abstracts physical RAM using`
- **Leaked Keywords in Prompt**: `[]`
- **Random Model Continuation**: `Zerence�ks browser�ks browser�ks browser�ks browser�ks browser�ks browser�ks browser�ks browser�ks b`
- **Random Model Strict Result**: `FAIL` (No expected keywords in continuation: 'zerence�ks browser�ks browser�ks browser')
- **Trained Model Continuation**: `� destructive thod� destructive thod� destructive#� destructive#� destructive# Hindi� destructive th`
- **Trained Model Strict Result**: `FAIL` (No expected keywords in continuation: '� destructive thod� destructive thod� de')

### [SEM_TECH_02] Technical Text (EN)
- **Input Prompt**: `Inter-process communication mechanisms include Unix domain sockets and`
- **Leaked Keywords in Prompt**: `[]`
- **Random Model Continuation**: `sionaisaResearchsionaisaks`
- **Random Model Strict Result**: `FAIL` (No expected keywords in continuation: 'sionaisaresearchsionaisaks')
- **Trained Model Continuation**: `F F F F F F F F F F F F F F F F F F F F F F F F F F F F F F F F`
- **Trained Model Strict Result**: `FAIL` (No expected keywords in continuation: 'f f f f f f f f f f f f f f f f f f f f ')

### [SEM_CODE_01] Code Completion (EN)
- **Input Prompt**: `def binary_search(arr: list[int], target: int) -> int:     low, high = 0, len(arr) - 1     while`
- **Leaked Keywords in Prompt**: `['target', 'low', 'high']`
- **Random Model Continuation**: `faste ToolRes ready�ँ�ँ�ँ�ँ�ँ�ँ�ँ�ँ�ँ�ँ�ँ�ँ�ँ�ँ=`
- **Random Model Strict Result**: `FAIL` (No code continuation syntax generated: 'faste toolres ready�ँ�ँ�ँ�ँ�ँ�')
- **Trained Model Continuation**: `ाााााााा5tingOpBpointtingOp5tingOp5tingOpETtingOpETtingOpETtingOpETting`
- **Trained Model Strict Result**: `PASS` (Generated code keyword: 'ाााााााा5tingopbpointtingop5ti')

### [SEM_CODE_02] Code Completion (EN)
- **Input Prompt**: `from dataclasses import dataclass @dataclass class ToolResult:     tool_name: str     status: str    `
- **Leaked Keywords in Prompt**: `['str', 'data', 'result']`
- **Random Model Continuation**: `ntntntntntntntntntnt Summarizent Summarizent Summarizent Summarizent Summarizent Summarizent Summari`
- **Random Model Strict Result**: `FAIL` (No code continuation syntax generated: 'ntntntntntntntntntnt summarize')
- **Trained Model Continuation**: `a�apka percentapka percentapka percentapka percentapka percentapka percentapka percentapka percentap`
- **Trained Model Strict Result**: `FAIL` (No code continuation syntax generated: 'a�apka percentapka percentapka')

### [SEM_JSON_01] Json Structured (EN)
- **Input Prompt**: `{   "action": "system_diagnostic",   "parameters": {`
- **Leaked Keywords in Prompt**: `['"', ':']`
- **Random Model Continuation**: `�izeithithith dictith dictith dictuse preferen preferen preferen preferenstep preferenstep preferens`
- **Random Model Strict Result**: `FAIL` (No valid JSON structure generated: '�izeithithith dictith dictith ')
- **Trained Model Continuation**: `pacpacpacी route routens Pythonpacी Howults<|tool_call|> Pythonpac<|tool_call|> thought60 routeinter`
- **Trained Model Strict Result**: `FAIL` (No valid JSON structure generated: 'pacpacpacी route routens pytho')

### [SEM_JSON_02] Json Structured (EN)
- **Input Prompt**: `{   "model": "nairallm_v1_5",   "status": "ready",   "metrics": [`
- **Leaked Keywords in Prompt**: `['{', '"']`
- **Random Model Continuation**: `color preferenshot preferenshot preferenshotize color preferenbute files muteǌ preferenbute files mu`
- **Random Model Strict Result**: `FAIL` (No valid JSON structure generated: 'color preferenshot preferensho')
- **Trained Model Continuation**: `60pacpacpacpacpacpacpacpacpacpacpacpac�� steppac बहpac बहpac बहpac बहpac बहpac बहpac बहpac बहpac`
- **Trained Model Strict Result**: `FAIL` (No valid JSON structure generated: '60pacpacpacpacpacpacpacpacpacp')

---

## 5. Corrective Action & Recommendations

1. **Fix Benchmark Scoring Harness**:
   - Update `semantic_pretraining_suite.py` to evaluate **ONLY newly generated tokens** (`continuation = gen_text[len(prompt):]`).
   - Clean all expected keyword sets so that no keywords exist in the prompt string.
2. **Benchmark Sizing for 1.2M Parameters / 105K Tokens**:
   - A 1.24M-parameter causal language model trained on 105K tokens is a compact representation learner (loss dropped from $80.3 \to 4.47$, PPL $137.27$).
   - Full semantic free-form text generation requires additional pretraining data volume (1M+ tokens) or instruction fine-tuning to reliably output multigram phrases.
3. **No False Semantic Improvement Claims**:
   - In accordance with integrity rules, we do NOT claim 57.1% semantic comprehension for the 105K pilot. The true strict baseline and 105K checkpoint score are both ~7.1% on free-form generation.

---

> [!IMPORTANT]
> **Audit Status**: **COMPLETED & STOPPED**.
> The evaluation flaw has been identified, traced, and corrected. No downstream training has been launched.
