"""
LLMPort — abstract interface every LLM provider adapter must implement.

21_System_Contracts.md §15 — LLM Provider Contracts.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from backend.types import LLMResponse, Message, ToolDef


class LLMPort(ABC):
    """Port that every LLM provider adapter must implement.

    Defined in the consumer module (``llm/``).  Adapters in
    ``llm/gemini_provider.py``, future ``providers/ollama.py``, etc.
    implement this interface.
    """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        context: list[Message],
        tools: list[ToolDef] | None = None,
    ) -> LLMResponse:
        """Send a prompt + conversation history to the LLM and return a response.

        Parameters
        ----------
        prompt : str
            System prompt / instruction text.
        context : list[Message]
            Conversation history (user + assistant turns).
        tools : list[ToolDef] | None
            Available tool definitions for function calling.

        Returns
        -------
        LLMResponse
            The model's response, including optional tool calls.
        """

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        context: list[Message],
        tools: list[ToolDef] | None = None,
    ) -> AsyncIterator[str]:
        """Stream response tokens from the LLM.

        Parameters
        ----------
        prompt : str
            System prompt / instruction text.
        context : list[Message]
            Conversation history.
        tools : list[ToolDef] | None
            Available tool definitions.

        Yields
        ------
        str
            Successive text chunks from the model.
        """

    @abstractmethod
    async def count_tokens(self, text: str) -> int:
        """Estimate the token count for a given text string.

        Parameters
        ----------
        text : str
            The input text to tokenise.

        Returns
        -------
        int
            Estimated token count.
        """
