"""
ContextBuilder — assembles an immutable ``Context`` for LLM consumption.

19_Request_Lifecycle.md §3 (Phase 3: Context Assembly).
"""

from __future__ import annotations

from backend.types import Context, Message


class ContextBuilder:
    """Builder for the ``Context`` dataclass consumed by the LLM pipeline.

    Accepts conversation history and a system prompt, applies token
    estimation, and returns an immutable ``Context`` payload.
    """

    @staticmethod
    def build(
        *,
        system_prompt: str,
        messages: list[Message],
        max_tokens: int = 4096,
    ) -> Context:
        """Assemble a ``Context`` from the given parts.

        Parameters
        ----------
        system_prompt : str
            System instruction for the LLM.
        messages : list[Message]
            Conversation history (pre-windowed if desired).
        max_tokens : int
            Maximum allowed token budget (used for estimation only;
            does **not** apply the sliding window).

        Returns
        -------
        Context
            Immutable context payload ready for prompt compilation.
        """
        token_count = ContextBuilder._count_tokens(system_prompt, messages)

        return Context(
            system_prompt=system_prompt,
            messages=list(messages),
            token_count=token_count,
        )

    @staticmethod
    def _count_tokens(system_prompt: str, messages: list[Message]) -> int:
        total = ContextBuilder._estimate_tokens(system_prompt)
        for msg in messages:
            total += ContextBuilder._estimate_tokens(msg.content) + 4
        return total

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token count (~4 characters per token)."""
        return max(1, len(text) // 4)
