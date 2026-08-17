"""
Computational Linguistics & Deep Learning Foundations Domain Generator for Dataset A.
Generates comprehensive technical prose on Transformer architectures, RoPE embeddings, FlashAttention, and evaluation metrics.
"""

from __future__ import annotations

from typing import Any


def get_computational_linguistics_samples() -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []

    def add(sample_id: str, domain: str, lang: str, text: str, notes: str = "") -> None:
        samples.append({
            "id": sample_id,
            "domain": domain,
            "language": lang,
            "text": text.strip(),
            "provenance": {
                "provenance_id": f"prov_{sample_id}",
                "author": "nairallm_semantic_curator",
                "license": "Apache-2.0",
                "acquisition_method": "controlled_synthetic",
                "notes": notes or "Computational linguistics and deep learning foundational exposition",
            },
        })

    add(
        "sem_llm_001",
        "programming",
        "en",
        "The Scaled Dot-Product Attention mechanism computes context representations by comparing Query (Q) vectors against Key (K) vectors and weighting Value (V) vectors accordingly: Attention(Q, K, V) = softmax((Q K^T) / sqrt(d_k)) V. The scaling factor 1 / sqrt(d_k) prevents the dot products from growing excessively large in high dimensions (d_k), which would push the softmax activation function into regions with near-zero gradients (gradient vanishing). Multi-Head Attention projects queries, keys, and values into h distinct representation subspaces, enabling the network to attend simultaneously to information from different semantic positions.",
        "Scaled Dot-Product Attention mathematical derivation and multi-head projection",
    )

    add(
        "sem_llm_002",
        "programming",
        "en",
        "Rotary Position Embedding (RoPE) incorporates relative positional information directly into Transformer self-attention by rotating the query and key representations in the complex plane. Unlike absolute positional embeddings (which add fixed or learned position vectors to token embeddings at the input layer), RoPE applies a 2D rotation matrix to paired channels of the query and key vectors. The dot product between rotated query q_m and key k_n depends exclusively on the relative distance (m - n), offering smooth position extrapolation to longer sequence lengths without retraining.",
        "Rotary Position Embedding (RoPE) relative position mathematics",
    )

    add(
        "sem_llm_003",
        "operating_systems",
        "en",
        "FlashAttention is an IO-aware exact self-attention algorithm that drastically accelerates Transformer training and inference on modern GPUs by minimizing High Bandwidth Memory (HBM) read/write bottlenecks. Standard self-attention materializes the full N x N attention matrix in global GPU HBM, inducing massive memory bandwidth overhead. FlashAttention tiles the Q, K, and V matrices into smaller blocks that fit entirely within fast on-chip SRAM cache, computing softmax incrementally via online softmax normalization and fusing memory operations, reducing memory complexity from O(N^2) to O(N).",
        "FlashAttention IO-aware memory tiling and online softmax on GPUs",
    )

    add(
        "sem_llm_004",
        "programming",
        "en",
        "KV Caching is the foundational memory optimization for autoregressive language model text generation. During the prefill stage, the model processes prompt tokens in parallel and caches the Key and Value projection tensors for all Transformer attention layers in GPU memory. During subsequent token-by-token decoding steps, the model only computes Q, K, and V for the single newly generated token, concatenating the new K and V tensors to the persistent KV Cache rather than re-computing representations for all preceding historical tokens, reducing per-token decoding complexity from O(N^2) to O(N).",
        "KV Cache architecture and autoregressive decoding complexity",
    )

    add(
        "sem_llm_005",
        "hindi_linguistics",
        "hi",
        "देवनागरी लिपि में 'अक्षर' (Akshara) ध्वन्यात्मकता (Phonetics) की दृष्टि से अत्यंत वैज्ञानिक और सुव्यवस्थित इकाई है। प्रत्येक देवनागरी व्यंजन में डिफ़ॉल्ट रूप से अंतर्निहित 'अ' स्वर मौजूद होता है। जब किसी व्यंजन को स्वर-रहित करना होता है, तो 'हलंत' (् - Virama) का उपयोग किया जाता है। संयुक्त व्यंजन (जैसे क् + ष = क्ष, त् + र = त्र, ज् + ञ = ज्ञ) दो या अधिक व्यंजनों के बिना स्वर के मेल से बनते हैं। नुक्ता (़) का प्रयोग विदेशी ध्वनियों (जैसे क़, ख़, ग़, ज़, फ़) को दर्शाने के लिए किया जाता है। यह सटीक ध्वन्यात्मक व्यवस्था देवनागरी को कंप्यूटर प्रसंस्करण और स्पीच-टू-टेक्स्ट इंजनों के लिए अत्यधिक उपयुक्त बनाती है।",
        "Devanagari Akshara phonetics, Virama halant, and conjuncts in Hindi",
    )

    add(
        "sem_llm_006",
        "hinglish_discourse",
        "hinglish",
        "LLM inference serving optimize karte time continuous batching (iteration-level scheduling) use kiya jata hai. Traditional static batching me agar ek batch ke andar alag-alag request sequence lengths hon, toh short requests complete hone ke baad bhi longest request finish hone tak GPU idle wait karti rehti hai. vLLM aur TensorRT-LLM jaise modern inference engines PagedAttention use karke dynamic token allocation manage karte hain, jisse GPU compute utilization 90%+ maintain rehti hai aur throughput 4x-8x boost ho jata hai.",
        "LLM inference continuous batching and PagedAttention in Hinglish",
    )

    add(
        "sem_llm_007",
        "software_engineering",
        "en",
        "Chaos Engineering is the discipline of experimenting on a distributed software system in production to build confidence in the system's capability to withstand turbulent unexpected conditions. Principles include: defining steady state metrics (such as order checkout rate or HTTP error percentage), hypothesizing that steady state will continue despite disruptions, introducing realistic simulated failures (such as randomly terminating Kubernetes worker nodes, injecting network packet loss, simulating cross-region DNS outages), and verifying automated recovery mechanisms without customer-facing degradation.",
        "Chaos Engineering principles, fault injection, and steady state verification",
    )

    add(
        "sem_llm_008",
        "databases",
        "en",
        "Database Write Amplification Factor (WAF) is a critical performance metric defined as the ratio of total bytes written to non-volatile persistent storage relative to the logical bytes written by the user application: WAF = Bytes Written to Disk / Logical Bytes Written. In relational B-Tree databases, modifying a single 20-byte row can trigger full 8 KB page writes to the Write-Ahead Log (WAL) and subsequent page flushes to data tables (WAF > 10). In LSM-Tree storage engines, iterative background compaction across multiple levels also contributes to write amplification, requiring careful tuning of compaction strategies (Size-Tiered vs Leveled).",
        "Write Amplification Factor (WAF) in B-Trees and LSM-Trees",
    )

    return samples
