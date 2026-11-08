"""
Interfaces for the model providers.

The rest of the code depends only on these, so a provider (fake, Gemini, Groq,
Bedrock …) can be swapped by adding one class and changing `LLM_PROVIDER`.
"""

from collections.abc import Sequence
from typing import Protocol


class Embedder(Protocol):
    """Turns text into vectors. Similar meaning → similar vectors."""

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class ChatModel(Protocol):
    """Generates text from a system prompt and a user prompt."""

    def generate(self, system: str, prompt: str) -> str: ...
