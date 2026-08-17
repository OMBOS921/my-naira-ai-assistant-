# NairaLLM V1.4 Generalization & Structured Cognition Report

## 1. Executive Summary

| Model Version | Capacity (Params) | Formulation | 55 Unseen Generalization | Pass Rate |
|---|---|---|---|---|
| **V1 Baseline** | 275K | Direct JSON Generation | **8/55** | **14.5%** |
| **V1.1 Model** | 275K | Direct JSON Generation | **4/55** | **7.3%** |
| **V1.2 Model (275K params)** | 275K | Direct JSON Generation | **6/55** | **10.9%** |
| **V1.3 Small (1.43M params)** | 1.43M | Direct JSON Generation | **1/55** | **1.8%** |
| **V1.3 Medium (7.06M params)** | 7.06M | Direct JSON Generation | **2/55** | **3.6%** |
| **V1.4 Structured Cognition** | 275K | Structured Cognition (<|intent|> → <|tool_call|>) | **1/55** | **1.8%** |

## 2. Structured Cognition Metrics (V1.4)

- **Total Structured Tests**: 22
- **Passed Tests**: 2 (9.1%)
- **Intent Recognition Accuracy**: 0.0%
- **Tool Selection Accuracy**: 31.8%
- **Structured Control Token Validity**: 95.5%

## 3. V1.4 Category Breakdown on 55 Unseen Tests

| Category | Passed | Total | Accuracy |
|---|---|---|---|
| browser | 0 | 3 | 0.0% |
| tool_selection | 0 | 22 | 0.0% |
| memory | 0 | 7 | 0.0% |
| coding | 0 | 6 | 0.0% |
| planning | 0 | 2 | 0.0% |
| safety | 0 | 7 | 0.0% |
| conversation | 1 | 8 | 12.0% |
