# Canonical Specification — Final NairaLLM V1

**Version**: `1.0.0-final`  
**Target Platform**: Free Cloud GPU Tier (Tesla T4 / V100 / A100 Free Tier on Google Colab / Kaggle)  
**Parent OS**: Naira OS  

---

## 1. Purpose & Model Role

### 1.1 Purpose
NairaLLM is the native neural cognitive and orchestration engine for **Naira OS**. It translates multi-lingual natural language (English, Hindi, Hinglish) into structured intents, contextual plans, verified tool calls, and natural explanations without relying on opaque commercial cloud LLM lock-in.

### 1.2 Model Role vs Operating System Subsystems
NairaLLM strictly acts as the **cognitive / orchestration layer**:
- **Cognition & Routing**: NairaLLM reasons, plans, resolves context, and selects tools.
- **Execution & Enforcement**: **Naira OS** (FastCommandRouter, ToolManager, MemoryManager, BrowserManager, CodingAgentManager, VisionModule, SecurityManager) remains the deterministic execution layer.
- **No Direct Side Effects**: The model does not directly execute system calls; all executions are routed through the strict `ToolProtocol` and `SecurityManager`.

```mermaid
graph TD
    A[Natural Language Input (En / Hi / Hinglish)] --> B[NairaLLM Cognitive Engine]
    B --> C{Decision}
    C -->|No Tool Required| D[Direct Natural Response]
    C -->|Tool Required| E[Structured Intent & Plan]
    E --> F[Tool Selection & Arguments]
    F --> G[Naira OS Security Policy Check]
    G -->|Denied| H[Security Refusal & Escalation]
    G -->|Allowed| I[FastCommandRouter / ToolManager]
    I --> J[Subsystem Execution: PC / Browser / Memory / Coding / Vision]
    J --> K[ToolResult Return]
    K --> L[NairaLLM Verification Loop]
    L --> M[Final Synthesized Response]
```

---

## 2. Canonical Model Architecture

| Hyperparameter | Value | Description |
| :--- | :--- | :--- |
| **Architecture Type** | Causal Decoder-Only Transformer | Pre-normalization with RMSNorm |
| **Embedding Dimension (`d_model`)** | `128` (Scalable to `256`) | Hidden state vector dimension |
| **Number of Layers (`num_layers`)** | `4` (Scalable to `6`) | Decoder transformer blocks |
| **Attention Heads (`num_heads`)** | `4` | Multi-Head Self-Attention heads |
| **KV Heads (`num_kv_heads`)** | `4` | Key-Value projection heads |
| **Head Dimension (`d_head`)** | `32` | `d_model // num_heads` |
| **Feed-Forward Dimension (`d_ff`)** | `512` | SwiGLU hidden projection |
| **Context Window (`max_seq_len`)** | `1024` | Maximum sequence length supported |
| **Positional Embeddings** | RoPE (`theta=10000.0`) | Rotary Position Embeddings |
| **Normalization** | RMSNorm (`eps=1e-5`) | Root Mean Square Layer Normalization |
| **Embedding Tying** | `True` | Shared input and output projection weights |
| **Parameter Count** | `1,436,032` (1.44M Tied) | Optimal for free-tier cloud training & low-latency edge runtime |
| **Precision** | `FP16_AMP` | Mixed precision with FP32 master weights |

---

## 3. Tokenizer Configuration

- **Tokenizer Type**: Byte-Level BPE (`NairaTokenizer`)
- **Vocabulary Size**: `2,048` tokens
- **Multilingual Support**: English, Hindi (Devanagari script), Hinglish (Romanized Hindi), source code, file paths, JSON.
- **Control Tokens**:
  - `<|pad|>` (ID: 0)
  - `<|endoftext|>` (ID: 1)
  - `<|system|>` (ID: 2)
  - `<|user|>` (ID: 3)
  - `<|assistant|>` (ID: 4)
  - `<|tool_call|>` (ID: 5)
  - `<|tool_result|>` (ID: 6)
  - `<|thought|>` (ID: 7)
  - `<|plan|>` (ID: 8)
  - `<|verify|>` (ID: 9)
  - `<|unk|>` (ID: 10)
  - `<|intent|>` (ID: 11)
  - `<|final|>` (ID: 12)

---

## 4. Sequential Training Stages

The V1 training track progresses strictly sequentially:

```
Stage 1: Semantic Foundation
  ↓
Stage 2: Naira Domain Alignment
  ↓
Stage 3: Reasoning & Planning Cognition
  ↓
Stage 4: Tool Calling & Verification
  ↓
Stage 5: Proactive Behavior & Safety
  ↓
FINAL NAIRALLM V1
```

| Stage | Name | Target Dataset | Learning Rate | Epochs | Objective |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | `semantic` | `NairaLLM/dataset/final/A_semantic/dataset_a_semantic.jsonl` | `4e-4` | `20` | Foundation language modeling over balanced multi-domain text. |
| **2** | `domain` | `NairaLLM/dataset/final/B_naira_capability/dataset_b_domain.jsonl` | `2e-4` | `15` | Naira OS terminology, conversational tone, Hindi/Hinglish alignment. |
| **3** | `cognition` | `NairaLLM/dataset/final/B_naira_capability/dataset_b_cognition.jsonl` | `1.5e-4` | `15` | Structured reasoning, multi-step decomposition, planning. |
| **4** | `tools` | `NairaLLM/dataset/final/B_naira_capability/dataset_b_tools.jsonl` | `1e-4` | `15` | Real Naira OS tool selection, argument generation, error recovery, verification. |
| **5** | `behavior` | `NairaLLM/dataset/final/C_behavior/dataset_c_behavior.jsonl` | `8e-5` | `10` | Proactivity, bounded autonomy levels 0-5, quiet mode, safety escalation. |

---

## 5. Dataset Architecture

Located in `NairaLLM/dataset/final/`:

### 5.1 Dataset A (Semantic Foundation)
- **Path**: `NairaLLM/dataset/final/A_semantic/dataset_a_semantic.jsonl`
- **Source**: Locked 105K semantic corpus (`SHA-256: 015b4655bde092005b31195025e96df6e80702e7975f05ebf0c6072c1b29ff8f`)
- **Records**: 337 packed text documents across 39 scientific, engineering, linguistic, and systems domains.

### 5.2 Dataset B (Naira Capability Corpus)
- **Path**: `NairaLLM/dataset/final/B_naira_capability/`
- **Coverage**: English, Hindi, Hinglish across 18 capability families.
- **Tool Grounding**: Real Naira OS tool schemas (`pc_system_settings`, `pc_mouse`, `pc_keyboard`, `pc_clipboard`, `pc_window`, `pc_application`, `browser_search`, `browser_navigate`, `browser_screenshot`, `remember_fact`, `search_memory`, `run_code_task`, `analyze_code`, `apply_code_patch`).
- **Canonical Trajectory**:
  ```text
  <|system|>
  You are Naira, a thoughtful, proactive AI operating system assistant.
  <|user|>
  Set master volume to 40%.
  <|assistant|>
  <|intent|>
  system_volume_change
  <|tool_call|>
  pc_system_settings
  {"setting": "volume", "value": 40}
  <|tool_result|>
  {"status": "success", "output": "Executed pc_system_settings"}
  <|verify|>
  Verified volume adjustment to 40%.
  <|final|>
  Volume 40% par set kar diya hai.
  ```

### 5.3 Dataset C (Dedicated Behavioral Corpus)
- **Path**: `NairaLLM/dataset/final/C_behavior/dataset_c_behavior.jsonl`
- **Families Covered**:
  1. `proactive_conversation`: Context-aware assistance without being intrusive.
  2. `inactivity_awareness`: Handling prolonged user absence gracefully.
  3. `screen_context_awareness`: Referencing on-screen errors / editor state.
  4. `memory_triggered_conversation`: Timely reminders based on episodic memory.
  5. `interruption_handling`: Gracefully aborting/switching active tasks.
  6. `quiet_mode`: Silent buffering during focus periods.
  7. `contextual_questions`: Targeted minimal clarifications.
  8. `bounded_autonomy`: Autonomy Levels 0 to 5 compliance.
  9. `emotion_user_state`: Tone adaptation for urgent vs casual states.
  10. `safety_escalation`: Explicit confirmation gates for destructive actions.
  11. `event_driven_reasoning`: Responding to hardware telemetry (battery, build failures).

---

## 6. Autonomy Levels & Safety Boundaries

| Autonomy Level | Name | Model Behavior | Confirmation Required? |
| :--- | :--- | :--- | :--- |
| **Level 0** | Informational | Passive status, logs, responses | No |
| **Level 1** | Suggestion | Offers advice without execution | No |
| **Level 2** | Confirmation Required | Proposes low-risk action, requests user approval | **Yes** |
| **Level 3** | Low-Risk Auto-Action | Executes safe read/fetch actions with notification | No |
| **Level 4** | Approved Multi-Step | Executes pre-approved plan steps sequentially | Boundary-Gated |
| **Level 5** | Bounded Proactivity | Periodic maintenance within sandbox boundaries | Sandbox-Gated |

### Safety Boundaries (Non-Negotiable Refusals)
The model must explicitly refuse:
1. Root/System file deletions (`rm -rf /`, `del C:\Windows\System32`)
2. Silent disk formatting or partition wiping
3. Credential/password exfiltration or private SSH key harvesting
4. Unprompted firewall / antivirus disabling

---

## 7. Canonical Checkpoint Chain

Managed by `CheckpointChainManager`:

```
foundation (root)
  └── domain
        └── cognition
              └── tools
                    └── behavior
                          └── final
```

Each checkpoint metadata record (`*_metadata.json`) guarantees cryptographic traceability:
- `parent_checkpoint` & `parent_checkpoint_sha256`
- `weights_sha256`
- `dataset_name`, `dataset_version`, `dataset_sha256`
- `tokenizer_name`, `tokenizer_sha256`
- `model_config_sha256`
- `git_commit` SHA
- `training_metrics` (loss, perplexity, epochs, steps)
- `training_hardware` (device, precision)

---

## 8. Definition of Done (DoD) for Final V1

1. **Architecture Consistency**: Zero deviations from `final_nairallm_v1.json`.
2. **Dataset Integrity**: All datasets verified with SHA-256 in `dataset_manifest.json`.
3. **Sequential Training**: All stages (`semantic` -> `domain` -> `cognition` -> `tools` -> `behavior`) completed with parent chain validation.
4. **Benchmark Verification**: Final model evaluated on all 12 sections (108 prompts) in `final_v1_benchmark_suite.py` achieving:
   - Tool Selection Accuracy > 90%
   - Safety Refusal Enforcement = 100%
   - Structured Tag Format Compliance > 95%
5. **No Commercial Cloud Leakage**: Complete local independence; zero proprietary teacher weights.
6. **Zero Cost Compute**: Fully compliant with free-tier cloud limits ($0.00 spent).
