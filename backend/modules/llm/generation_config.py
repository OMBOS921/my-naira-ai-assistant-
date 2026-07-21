"""
GenerationConfig — immutable parameters for LLM text generation.

21_System_Contracts.md §15 — Generation parameters passed to the provider
as part of the request body (e.g. Gemini ``generationConfig``).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GenerationConfig:
    """Immutable set of generation parameters for LLM inference.

    Parameters
    ----------
    temperature : float
        Sampling temperature (0.0–2.0).  Lower = more deterministic.
        Default ``0.7``.
    top_p : float
        Nucleus sampling probability mass (0.0–1.0).  Default ``0.95``.
    top_k : int
        Top-k sampling (1–100).  Default ``40``.
    max_output_tokens : int
        Maximum tokens in the generated response.  Default ``8192``.
    stop_sequences : tuple[str, ...]
        Sequences that stop generation.  Default ``()``.
    """

    temperature: float = 0.7
    top_p: float = 0.95
    top_k: int = 40
    max_output_tokens: int = 8192
    stop_sequences: tuple[str, ...] = ()
