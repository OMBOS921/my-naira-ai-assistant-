"""
Science, Mathematics, & Information Theory Domain Generator for Dataset A.
Generates comprehensive technical prose on Shannon entropy, linear algebra, calculus, probability distributions, and logic.
"""

from __future__ import annotations

from typing import Any


def get_science_math_samples() -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []

    def add(sample_id: str, text: str, notes: str = "") -> None:
        samples.append({
            "id": sample_id,
            "domain": "natural_language",
            "language": "en",
            "text": text.strip(),
            "provenance": {
                "provenance_id": f"prov_{sample_id}",
                "author": "nairallm_semantic_curator",
                "license": "Apache-2.0",
                "acquisition_method": "controlled_synthetic",
                "notes": notes or "Mathematics, information theory, and scientific foundations exposition",
            },
        })

    add(
        "sem_math_001",
        "Shannon Entropy, formulated by Claude Shannon in 1948, quantifies the fundamental limit of expected information content, uncertainty, or surprise contained in a stochastic source message. Mathematically defined as H(X) = - Σ P(x) log2 P(x), entropy reaches its maximum when all outcome states are equally probable (uniform distribution). In data compression algorithms like Huffman coding and Arithmetic coding, Shannon's source coding theorem establishes that a message cannot be compressed into fewer average bits per symbol than the source's Shannon entropy without loss of information.",
        "Shannon entropy formula and source coding theorem limits",
    )

    add(
        "sem_math_002",
        "Singular Value Decomposition (SVD) is a fundamental matrix factorization theorem in linear algebra stating that any real m x n matrix A can be factored as A = U Σ V^T, where U is an m x m orthogonal matrix of left-singular vectors, Σ is an m x n rectangular diagonal matrix containing non-negative singular values ordered by magnitude, and V is an n x n orthogonal matrix of right-singular vectors. SVD provides the mathematical foundation for Principal Component Analysis (PCA), low-rank matrix approximation, pseudoinverse computation, and recommendation engines.",
        "Singular Value Decomposition (SVD) matrix factorization and PCA",
    )

    add(
        "sem_math_003",
        "The Central Limit Theorem (CLT) is a cornerstone of probability theory asserting that when independent, identically distributed (i.i.d.) random variables with finite variance are summed, their normalized sum converges in distribution to a standard Gaussian (Normal) bell curve, regardless of the underlying distribution of the original variables. This mathematical truth explains why normal distributions appear ubiquitously across natural sciences, measurement errors, physical particle velocities, and statistical quality control.",
        "Central Limit Theorem (CLT) and Gaussian convergence",
    )

    add(
        "sem_math_004",
        "Gradient Descent is a first-order iterative optimization algorithm used to find the local minimum of a differentiable mathematical function. At each step, the algorithm computes the vector of partial derivatives (the gradient ∇f) of the loss function with respect to parameter weights and updates weights in the opposite direction scaled by a learning rate hyperparameter: θ = θ - η ∇f(θ). Stochastic Gradient Descent (SGD) and adaptive optimizers like Adam incorporate momentum and exponentially decaying running averages of squared gradients to navigate ravines and saddle points efficiently.",
        "Gradient Descent optimization mechanics and Adam momentum equations",
    )

    return samples
