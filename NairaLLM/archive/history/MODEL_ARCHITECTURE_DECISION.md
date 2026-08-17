# Model Architecture Decision Document

## 1. Context & Objectives
NairaLLM is designed as a small, specialized, self-owned language model for Naira OS. It provides reasoning, task planning, structured tool invocation, verification, memory interaction, and bounded proactive behaviors.

Key design criteria:
- **Low Parameter Count & Memory Footprint**: Compact causal decoder (~15M - 35M parameters in prototype configuration) enabling fast CPU execution under 500MB RAM.
- **Causal Auto-regressive Generation**: Decoder-only architecture with causal attention masking.
- **Modern Transformer Innovations**:
  - **Rotary Position Embeddings (RoPE)**: Eliminates fixed absolute position limits, improving generalization across prompt lengths.
  - **RMSNorm**: Faster and more numerically stable than standard LayerNorm.
  - **SwiGLU Activation**: Superior representation capacity compared to standard ReLU/GELU in feed-forward layers.
  - **KV Caching**: Constant per-token latency during autoregressive token generation.
- **Dual-Backend Runtime**: Implements standard PyTorch neural modules and a lightweight NumPy execution path for maximum deployment flexibility.

---

## 2. Architecture Specifications (Prototype V1)

| Parameter | Default Value (Prototype V1) | Purpose / Description |
| :--- | :--- | :--- |
| `vocab_size` | 2,048 (dynamic) | Covers English, Hindi, Hinglish, Code, and Control tokens |
| `d_model` | 256 | Hidden dimension |
| `num_layers` | 6 | Number of Transformer Decoder blocks |
| `num_heads` | 8 | Number of Multi-Head Attention heads (`d_head = 32`) |
| `num_kv_heads` | 8 | Grouped/Multi-Query KV heads |
| `d_ff` | 684 | SwiGLU hidden dimension (`~ 8/3 * d_model`) |
| `max_seq_len` | 1,024 | Maximum context window |
| `norm_eps` | 1e-5 | RMSNorm epsilon |
| `rope_theta` | 10,000.0 | Base frequency for RoPE |
| `tie_embeddings` | `True` | Weight tying between input embeddings and output head |

---

## 3. Special Control Tokens
- `<|pad|>` (0): Padding token for batch alignment.
- `<|endoftext|>` (1): End-of-sequence delimiter.
- `<|system|>` (2): Demarcates system instructions.
- `<|user|>` (3): Demarcates user turns.
- `<|assistant|>` (4): Demarcates assistant turns.
- `<|tool_call|>` (5): Initiates structured tool invocation payload.
- `<|tool_result|>` (6): Encloses structured tool results returned by Naira OS.
- `<|thought|>` (7): Encapsulates internal cognitive reasoning.
- `<|plan|>` (8): Outlines multi-step task decomposition.
- `<|verify|>` (9): Declares outcome verification checks.

---

## 4. Verification and Benchmark Protocol
1. Exact reconstruction of structured JSON tool calls.
2. Zero hallucinations on verified tool outputs.
3. Stable cross-entropy loss convergence (< 1.5) on domain datasets.
