"""
Interfaces for the model providers.

The rest of the code depends only on these, so a provider (fake, Gemini, Groq,
Bedrock …) can be swapped by adding one class and changing `LLM_PROVIDER`.
"""

from collections.abc import Sequence
from typing import Protocol


class Embedder(Protocol):
    """
    Turns text into vectors. Similar meaning gives similar vectors.

    Documents and queries are embedded separately because some models (Gemini
    included) encode them differently to improve search quality.
    """

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class ChatModel(Protocol):
    """Generates text from a system prompt and a user prompt."""

    def generate(self, system: str, prompt: str) -> str: ...


class ProviderError(Exception):
    """The model provider failed. The message is safe to show to users."""


class ProviderRateLimited(ProviderError):
    """The provider's quota is used up for now (HTTP 429). `retry_after` is in seconds, when known."""

    def __init__(self, message: str | None = None, retry_after: int | None = None) -> None:
        self.retry_after = retry_after
        if message is None:
            wait = f"in about {retry_after} seconds" if retry_after else "in a minute"
            message = f"The free AI quota is used up for the moment. Try again {wait}."
        super().__init__(message)
