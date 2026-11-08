"""
Google Gemini provider (free tier, no credit card needed).

Get a key at https://aistudio.google.com/apikey and set GEMINI_API_KEY.
Free-tier limits are per minute and per day; see them in AI Studio. On the free
tier Google may use prompts to improve its products, so don't upload anything
sensitive to a public demo.
"""

import logging
import math
from collections.abc import Iterator, Sequence
from contextlib import contextmanager

from google import genai
from google.genai import errors, types

from api.providers.base import ProviderError, ProviderRateLimited

logger = logging.getLogger(__name__)

# The API accepts up to 100 texts per embedding request.
MAX_EMBED_BATCH = 100
RATE_LIMITED_MESSAGE = "The free AI quota is used up for the moment. Wait a minute and try again."
UNAVAILABLE_MESSAGE = "The AI service is unavailable right now. Try again shortly."


def create_client(api_key: str) -> genai.Client:
    # Retries 429 and 5xx responses with exponential backoff before giving up.
    retry = types.HttpRetryOptions(attempts=3, initial_delay=1.0, max_delay=8.0)
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(retry_options=retry, timeout=60_000))


class GeminiChatModel:
    def __init__(self, client: genai.Client, model: str, thinking_level: str | None = None) -> None:
        self.client = client
        self.model = model
        self.thinking_level = thinking_level

    def generate(self, system: str, prompt: str) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.2,
            thinking_config=types.ThinkingConfig(thinking_level=self.thinking_level)
            if self.thinking_level
            else None,
        )
        with _translate_errors():
            response = self.client.models.generate_content(model=self.model, contents=prompt, config=config)
        if not response.text:
            raise ProviderError("The AI returned an empty answer. Try rephrasing the question.")
        return response.text.strip()


class GeminiEmbedder:
    """Uses gemini-embedding-001, which takes a task type and needs manual normalisation below 3072 dims."""

    def __init__(self, client: genai.Client, model: str, dimensions: int) -> None:
        self.client = client
        self.model = model
        self.dimensions = dimensions

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), MAX_EMBED_BATCH):
            vectors.extend(self._embed(list(texts[start : start + MAX_EMBED_BATCH]), "RETRIEVAL_DOCUMENT"))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], "RETRIEVAL_QUERY")[0]

    def _embed(self, texts: list[str], task_type: str) -> list[list[float]]:
        config = types.EmbedContentConfig(task_type=task_type, output_dimensionality=self.dimensions)
        with _translate_errors():
            response = self.client.models.embed_content(model=self.model, contents=texts, config=config)
        embeddings = response.embeddings or []
        if len(embeddings) != len(texts):
            raise ProviderError(UNAVAILABLE_MESSAGE)
        return [normalize(list(embedding.values or [])) for embedding in embeddings]


def normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


@contextmanager
def _translate_errors() -> Iterator[None]:
    """Turns SDK errors into ProviderError so callers don't depend on the SDK."""
    try:
        yield
    except errors.APIError as error:
        logger.warning("Gemini API error %s: %s", error.code, error)
        if error.code == 429:
            raise ProviderRateLimited(RATE_LIMITED_MESSAGE) from error
        raise ProviderError(UNAVAILABLE_MESSAGE) from error
