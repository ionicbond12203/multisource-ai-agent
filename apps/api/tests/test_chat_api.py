from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from helpers import upload
from pdf_factory import make_pdf

from api.graph.build import NO_FILES_ANSWER, NOT_FOUND_ANSWER, ChatAgent
from api.main import create_app
from api.providers.fake import HashingEmbedder
from api.store.memory import InMemoryVectorStore

SOP_PAGES = [
    "Cold chain SOP. Section 1 covers warehouse receiving and pallet checks.",
    "Section 4.2. Chilled RTD tea must be kept between 2 C and 8 C during last-mile delivery.",
]


def upload_id(client: TestClient, name: str, data: bytes) -> str:
    return upload(client, name, data)["id"]


def ask(client: TestClient, question: str, file_ids: list[str], history: list | None = None) -> dict:
    response = client.post(
        "/chat", json={"question": question, "fileIds": file_ids, "history": history or []}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_answer_cites_the_right_page(client):
    file_id = upload_id(client, "sop.pdf", make_pdf(SOP_PAGES))
    body = ask(client, "What temperature must chilled RTD tea be kept at?", [file_id])

    assert body["grounded"] is True
    assert "2 C and 8 C" in body["content"]
    assert "[1]" in body["content"]
    first = body["sources"][0]
    assert first["index"] == 1
    assert first["fileName"] == "sop.pdf"
    assert first["location"] == "Page 2 of 2"
    assert first["passages"][0]["cited"] is True


def test_trace_lists_every_node_in_order(client):
    file_id = upload_id(client, "sop.pdf", make_pdf(SOP_PAGES))
    run = ask(client, "chilled tea temperature", [file_id])["run"]
    assert [step["node"] for step in run["steps"]] == ["router", "retrieve", "answer", "verify_citations"]
    assert all(step["status"] == "done" for step in run["steps"])
    assert run["totalMs"] >= 0


def test_unrelated_question_is_not_found(client):
    file_id = upload_id(client, "sop.pdf", make_pdf(SOP_PAGES))
    body = ask(client, "Who won the football match yesterday?", [file_id])
    assert body["content"] == NOT_FOUND_ANSWER
    assert body["grounded"] is False
    assert body["sources"] == []
    assert [step["node"] for step in body["run"]["steps"]] == ["router", "retrieve"]


def test_no_files_selected(client):
    body = ask(client, "What temperature?", [])
    assert body["content"] == NO_FILES_ANSWER
    assert [step["node"] for step in body["run"]["steps"]] == ["router"]


def test_only_selected_files_are_searched(client):
    upload_id(client, "sop.pdf", make_pdf(SOP_PAGES))
    halal = upload_id(client, "halal.txt", b"Halal audits happen every quarter with form QA-07.")

    body = ask(client, "How often do halal audits happen?", [halal])
    assert {source["fileId"] for source in body["sources"]} == {halal}

    # The SOP covers this, but it is switched off, so the answer must not use it.
    assert ask(client, "chilled RTD tea last-mile delivery", [halal])["content"] == NOT_FOUND_ANSWER


class RecordingModel:
    """Chat model stub that returns a fixed answer and remembers the prompt."""

    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.prompt = ""

    def generate(self, system: str, prompt: str) -> str:
        self.prompt = prompt
        return self.answer


class FailingModel:
    def generate(self, system: str, prompt: str) -> str:
        raise RuntimeError("provider is down")


def client_with_model(settings, model) -> tuple[TestClient, object]:
    app = create_app(settings)
    services = app.state.services
    # Reuse the app's store so uploaded files are searchable by the stub agent.
    agent = ChatAgent(settings, HashingEmbedder(), model, services.pipeline.store)
    app.state.services = replace(services, agent=agent)
    return TestClient(app), model


def test_invented_citation_is_removed_and_marked_not_grounded(settings):
    client, _ = client_with_model(settings, RecordingModel("Keep it cold [1]. Also true [9]."))
    file_id = upload_id(client, "sop.pdf", make_pdf(SOP_PAGES))
    body = ask(client, "chilled tea temperature", [file_id])
    assert body["content"] == "Keep it cold [1]. Also true."
    assert body["grounded"] is False
    assert body["run"]["steps"][-1]["summary"] == "Removed 1 citation with no source"


def test_history_is_included_in_the_prompt(settings):
    client, model = client_with_model(settings, RecordingModel("Yes [1]."))
    file_id = upload_id(client, "sop.pdf", make_pdf(SOP_PAGES))
    history = [
        {"role": "user", "content": "Tell me about chilled tea"},
        {"role": "assistant", "content": "OK"},
    ]
    ask(client, "And its temperature?", [file_id], history)
    assert "User: Tell me about chilled tea" in model.prompt
    assert "Question: And its temperature?" in model.prompt


def test_provider_failure_returns_a_friendly_502(settings):
    client, _ = client_with_model(settings, FailingModel())
    file_id = upload_id(client, "sop.pdf", make_pdf(SOP_PAGES))
    response = client.post("/chat", json={"question": "chilled tea", "fileIds": [file_id], "history": []})
    assert response.status_code == 502
    assert response.json()["detail"] == "The assistant couldn't answer right now. Try again."


@pytest.mark.parametrize("question", ["", "x" * 2001])
def test_question_length_is_validated(client, question):
    response = client.post("/chat", json={"question": question, "fileIds": [], "history": []})
    assert response.status_code == 422


def test_cors_allows_the_frontend_origin(client):
    response = client.options(
        "/chat",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_vector_store_isolated_per_app(settings):
    # Each app instance gets its own store, so tests can't leak files into each other.
    first, second = create_app(settings), create_app(settings)
    assert first.state.services.pipeline.store is not second.state.services.pipeline.store
    assert isinstance(first.state.services.pipeline.store, InMemoryVectorStore)
