"""
Calls the real Gemini API. Skipped unless both are set:

    GEMINI_API_KEY=...   RUN_LIVE_TESTS=1   uv run pytest tests/test_gemini_live.py

Uses a little free-tier quota, so it never runs in CI.
"""

import math
import os

import pytest

from api.config import Settings
from api.providers import build_providers

pytestmark = pytest.mark.skipif(
    not (os.environ.get("GEMINI_API_KEY") and os.environ.get("RUN_LIVE_TESTS") == "1"),
    reason="set GEMINI_API_KEY and RUN_LIVE_TESTS=1 to call the real Gemini API",
)


@pytest.fixture(scope="module")
def providers():
    return build_providers(Settings(llm_provider="gemini", _env_file=None))


def test_similar_meaning_scores_higher(providers):
    embedder, _ = providers
    query = embedder.embed_query("How cold must chilled tea be kept?")
    related, unrelated = embedder.embed_documents(
        [
            "Chilled RTD tea must stay between 2 and 8 degrees Celsius.",
            "The office closes at 6 pm on Fridays.",
        ]
    )
    assert len(query) == 768
    assert math.isclose(math.hypot(*query), 1.0, rel_tol=1e-6)

    def cosine(a, b):
        return sum(x * y for x, y in zip(a, b, strict=True))

    assert cosine(query, related) > cosine(query, unrelated)


def test_chat_model_answers(providers):
    _, chat_model = providers
    answer = chat_model.generate("Reply with one word.", "What colour is the sky on a clear day?")
    assert answer
