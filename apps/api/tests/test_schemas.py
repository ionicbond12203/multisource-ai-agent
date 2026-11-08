"""The JSON must match the frontend's TypeScript types exactly."""

from pydantic import TypeAdapter

from api.schemas import AgentStep, AskRequest, DocumentResponse, FileStatus, Processing, Ready


def test_fields_are_camel_case_in_json():
    step = AgentStep(id="s1", node="router", summary="x", duration_ms=12, status="done")
    assert step.model_dump(mode="json") == {
        "id": "s1",
        "node": "router",
        "summary": "x",
        "durationMs": 12,
        "status": "done",
    }


def test_request_accepts_camel_case():
    request = AskRequest.model_validate({"question": "Hi?", "fileIds": ["doc_1"], "history": []})
    assert request.file_ids == ["doc_1"]


def test_file_status_is_picked_by_kind():
    adapter = TypeAdapter(FileStatus)
    assert isinstance(adapter.validate_python({"kind": "ready", "pages": 3, "chunks": 9}), Ready)
    assert isinstance(adapter.validate_python({"kind": "processing", "stage": "chunking"}), Processing)


def test_document_response_shape():
    body = DocumentResponse(id="doc_1", status=Ready(pages=2, chunks=5)).model_dump(mode="json")
    assert body == {"id": "doc_1", "status": {"kind": "ready", "pages": 2, "chunks": 5}}
