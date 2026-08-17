# NairaLLM — Start Here & Developer Guide

## 1. Project Mission
NairaLLM is an independent, self-owned language model built from scratch specifically for Naira OS. It operates as the local cognitive engine of Naira OS for natural language reasoning, task planning, structured tool invocation, intent recognition, memory operations, and safe system execution.

## 2. Core Architecture Rules
1. **Self-Owned Architecture**: Custom Causal Decoder-Only Transformer with RoPE, RMSNorm, SwiGLU, and KV caching.
2. **No Proprietary Distillation**: Zero student-teacher distillation from closed proprietary models. All data is verified and provenance-tracked.
3. **Dual Backend**: Pure-NumPy CPU execution engine for local development, unit tests, and debugging; PyTorch GPU engine for cloud pretraining and fine-tuning.
4. **Structured Cognition**: Intent-conditioned routing (`<|intent|> → <|tool_call|> → Arguments → <|verify|> → <|final|>`).

## 3. Directory Layout
- `NairaLLM/model/`: Architecture (`naira_transformer.py`), Tokenizer (`naira_tokenizer.py`), Runtime (`naira_runtime.py`, `numpy_backend.py`), Config (`model_config.py`).
- `NairaLLM/dataset/`: Semantic Pretraining Corpus (`dataset/semantic_corpus/`), Instruction Datasets (`dataset/reviewed/`), Provenance Registry (`dataset/provenance/`).
- `NairaLLM/training/`: GPU Trainer (`training/scripts/train_gpu.py`), Cloud Helpers (`training/cloud/`), Checkpoints (`training/checkpoints/`).
- `NairaLLM/evaluation/`: Generalization Suite (`model_generalization_suite.py`), Semantic Suite (`semantic_pretraining_suite.py`), Results (`evaluation/results/`).
- `NairaLLM/integration/`: Adapter linking model runtime with Naira OS (`naira_llm_adapter.py`) and Tool Protocol (`protocol.py`).

## 4. Getting Started Workflow
1. Verify Environment: `python NairaLLM/training/cloud/check_environment.py`
2. Run Pipeline Tests: `python -m pytest NairaLLM/tests/ -v`
3. Generate Semantic Corpus: `python -m NairaLLM.dataset.build_semantic_corpus`
4. Pretrain / Finetune on GPU: `python -m NairaLLM.training.scripts.train_gpu`
5. Run Evaluation Benchmark: `python -m NairaLLM.evaluation.suites.run_v1_4_generalization_evaluation`
