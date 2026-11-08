"""
Gemini provider tests against a stand-in client, so they run offline.
`test_gemini_live.py` checks the real API when a key is available.
"""

import math
from types import SimpleNamespace

import pytest
from google.genai import errors

from api.providers.base import ProviderError, ProviderRateLimited
from api.providers.gemini import MAX_EMBED_BATCH, GeminiChatModel, GeminiEmbedder


class StubModels:
    def __init__(self, text: str | None = "Answer [1].", error: Exception | None = None) -> None:
        self.text = text
        self.error = error
        self.calls: list[dict] = []

    def generate_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        if self.error:
            raise self.error
        return SimpleNamespace(text=self.text)

    def embed_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        if self.error:
            raise self.error
        # Unnormalised vectors, like gemini-embedding-001 returns below 3072 dims.
        return SimpleNamespace(embeddings=[SimpleNamespace(values=[3.0, 4.0]) for _ in contents])


def stub_client(models: StubModels) -> SimpleNamespace:
    return SimpleNamespace(models=models)


def api_error(code: int) -> errors.APIError:
    return errors.ClientError(code, {"error": {"code": code, "message": "x", "status": "X"}})


def test_chat_sends_system_prompt_and_returns_text():
    models = StubModels(text="  Keep it cold [1].  ")
    model = GeminiChatModel(stub_client(models), "gemini-test", thinking_level="low")
    assert model.generate("Be careful.", "Question: x") == "Keep it cold [1]."
    config = models.calls[0]["config"]
    assert config.system_instruction == "Be careful."
    assert config.thinking_config.thinking_level.value == "LOW"


def test_chat_without_thinking_level_sends_no_thinking_config():
    models = StubModels()
    GeminiChatModel(stub_client(models), "gemini-test", thinking_level=None).generate("s", "p")
    assert models.calls[0]["config"].thinking_config is None


def test_empty_answer_is_an_error():
    with pytest.raises(ProviderError):
        GeminiChatModel(stub_client(StubModels(text=None)), "m").generate("s", "p")


def test_quota_errors_become_rate_limited():
    model = GeminiChatModel(stub_client(StubModels(error=api_error(429))), "m")
    with pytest.raises(ProviderRateLimited):
        model.generate("s", "p")


def test_other_api_errors_become_provider_errors():
    model = GeminiChatModel(stub_client(StubModels(error=api_error(400))), "m")
    with pytest.raises(ProviderError) as raised:
        model.generate("s", "p")
    assert not isinstance(raised.value, ProviderRateLimited)


def test_embeddings_are_normalised_and_use_task_types():
    models = StubModels()
    embedder = GeminiEmbedder(stub_client(models), "gemini-embedding-001", dimensions=768)

    [vector] = embedder.embed_documents(["chunk"])
    assert math.isclose(math.hypot(*vector), 1.0)
    assert vector == [0.6, 0.8]
    assert models.calls[0]["config"].task_type == "RETRIEVAL_DOCUMENT"
    assert models.calls[0]["config"].output_dimensionality == 768

    embedder.embed_query("question")
    assert models.calls[1]["config"].task_type == "RETRIEVAL_QUERY"


def test_documents_are_embedded_in_batches():
    models = StubModels()
    embedder = GeminiEmbedder(stub_client(models), "m", dimensions=768)
    vectors = embedder.embed_documents([f"chunk {n}" for n in range(MAX_EMBED_BATCH + 5)])
    assert len(vectors) == MAX_EMBED_BATCH + 5
    assert [len(call["contents"]) for call in models.calls] == [MAX_EMBED_BATCH, 5]
