# Final NairaLLM V1 Model Configuration & Parameter Integrity Audit

**Audit Date**: 2026-08-17  
**Audit Status**: **VERIFIED CONSISTENT & MATHEMATICALLY PROVEN**  
**Canonical PyTorch Parameters**: **1,242,880** (Tied Embeddings)  
**Untied / Storage Array Footprint**: **1,436,032**  
**Tokenizer Vocabulary**: **1,509** (Locked Byte-Level BPE)  

---

## 1. Executive Summary

This audit resolves **Blocker 1 (Model Parameter Consistency)** by conducting a rigorous layer-by-layer parameter derivation of the canonical **NairaLLM V1** architecture and reconciling all historical references across configs, codebase, checkpoint metadata, and specifications.

---

## 2. Layer-by-Layer Mathematical Breakdown

Given the canonical hyperparameters:
- **`vocab_size`**: `1509` (locked in `naira_tokenizer.json`)
- **`d_model`**: `128`
- **`num_layers`**: `4`
- **`num_heads`**: `4` (`d_head = 32`)
- **`num_kv_heads`**: `4`
- **`d_ff`**: `512`
- **`tie_embeddings`**: `True`

### 2.1 Token Embeddings
$$\text{Parameters} = \text{vocab\_size} \times d_{\text{model}} = 1509 \times 128 = \mathbf{193,152}$$

### 2.2 Single Transformer Block (Repeated for 4 Layers)
Each decoder layer consists of:
1. **Attention Input Normalization (`RMSNorm`)**:
   $$\text{weight} = d_{\text{model}} = \mathbf{128}$$
2. **Causal Self-Attention (`Multi-Head Attention`)**:
   - $Q_{\text{proj}}$ (`nn.Linear(128, 128, bias=False)`): $128 \times 128 = 16,384$
   - $K_{\text{proj}}$ (`nn.Linear(128, 128, bias=False)`): $128 \times 128 = 16,384$
   - $V_{\text{proj}}$ (`nn.Linear(128, 128, bias=False)`): $128 \times 128 = 16,384$
   - $\text{Out}_{\text{proj}}$ (`nn.Linear(128, 128, bias=False)`): $128 \times 128 = 16,384$
   - **Subtotal Attention Parameters**: $\mathbf{65,536}$
3. **Feed-Forward Input Normalization (`RMSNorm`)**:
   $$\text{weight} = d_{\text{model}} = \mathbf{128}$$
4. **Gated Feed-Forward Network (`SwiGLU`)**:
   - $W_1$ (gate projection, $128 \to 512$, no bias): $128 \times 512 = 65,536$
   - $W_2$ (down projection, $512 \to 128$, no bias): $512 \times 128 = 65,536$
   - $W_3$ (up projection, $128 \to 512$, no bias): $128 \times 512 = 65,536$
   - **Subtotal SwiGLU Parameters**: $\mathbf{196,608}$

$$\text{Total Parameters per Layer} = 128 + 65,536 + 128 + 196,608 = \mathbf{262,400}$$

### 2.3 All 4 Decoder Layers
$$\text{Total for 4 Layers} = 4 \times 262,400 = \mathbf{1,049,600}$$

### 2.4 Final Layer Normalization
$$\text{Final RMSNorm} = d_{\text{model}} = \mathbf{128}$$

### 2.5 Output Language Modeling Head
- When **`tie_embeddings = True`**:
  `self.output.weight = self.tok_embeddings.weight` (Shared tensor in memory)
  $$\text{Additional Parameters} = \mathbf{0}$$
- When **`tie_embeddings = False`** (or counted as separate array in storage):
  $$\text{Additional Parameters} = 1509 \times 128 = \mathbf{193,152}$$

---

## 3. Total Parameter Reconciliation

$$\text{Canonical PyTorch Tied Parameters} = 193,152 + 1,049,600 + 128 + 0 = \mathbf{1,242,880}$$
$$\text{Untied / Storage Array Footprint} = 1,242,880 + 193,152 = \mathbf{1,436,032}$$

### 3.1 Explanation of Historical Variance
1. **Where did "1.44M" come from?**
   The NumPy saver serialized `tok_embeddings` and `output` as two distinct array files in `.npz` format, totaling 1,436,032 floats. Some documentation rounded this to "~1.44M".
2. **Where did "1,242,880" come from?**
   The active PyTorch `NairaTransformer` module ties the weights via `self.output.weight = self.tok_embeddings.weight`, resulting in exactly 1,242,880 unique trainable weights in the PyTorch optimizer graph.
3. **Where did "2048" vocab come from?**
   A placeholder from early prototype configuration templates. The locked production tokenizer (`naira_tokenizer.json`) has exactly 1,509 vocabulary tokens.

---

## 4. Alignment Matrix

| File / Component | Prior Value | Updated Canonical Value | Status |
| :--- | :--- | :--- | :--- |
| `NairaLLM/configs/final_nairallm_v1.json` | 2048 vocab / 1.44M tied | `vocab_size: 1509`, `tied: 1242880`, `untied: 1436032` | **VERIFIED** |
| `NairaLLM/model/config/model_config.py` | `vocab_size: 2048` | `vocab_size: 1509`, `d_model: 128`, `num_layers: 4` | **VERIFIED** |
| `NairaLLM/model/architecture/naira_transformer.py` | Tied embeddings | `tie_embeddings: true` ($1,242,880$ params) | **VERIFIED** |
| `NairaLLM/training/scripts/train_final_v1.py` | Dynamic lookup | Strict 1509 vocab and 1,242,880 param count | **VERIFIED** |
| `NairaLLM/docs/FINAL_NAIRALLM_V1_SPEC.md` | ~1.44M parameters | 1,242,880 tied parameters (1.44M untied) | **VERIFIED** |

---

## 5. Verification Sign-off

```python
# Empirical Verification in PyTorch:
model = NairaTransformer(NairaModelConfig(vocab_size=1509, d_model=128, num_layers=4, num_heads=4, d_ff=512, tie_embeddings=True))
assert model.count_parameters() == 1242880  # PASS
```

Blocker 1 is formally **RESOLVED and LOCKED**.
