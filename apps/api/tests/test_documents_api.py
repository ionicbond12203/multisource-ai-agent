from dataclasses import replace

from fastapi.testclient import TestClient
from helpers import upload
from pdf_factory import make_pdf

from api.config import Settings
from api.ingestion.pipeline import IngestionPipeline
from api.main import create_app
from api.providers.base import ProviderRateLimited


def test_pdf_is_processed_until_ready(client):
    pdf = make_pdf(["Cold chain policy.\nKeep chilled tea at 2 to 8 C.", "Second page about audits."])
    status = upload(client, "policy.pdf", pdf)["status"]
    assert status == {"kind": "ready", "pages": 2, "chunks": 2}


def test_upload_returns_immediately_with_processing_status(client):
    response = client.post("/documents", files={"file": ("notes.txt", b"Some useful notes here.")})
    assert response.status_code == 201
    body = response.json()
    assert body["id"].startswith("doc_")
    assert body["status"] == {"kind": "processing", "stage": "parsing"}


def test_text_and_markdown_files_are_supported(client):
    assert (
        upload(client, "notes.md", b"# Notes\nDrivers log temperatures hourly.")["status"]["kind"] == "ready"
    )


def test_scanned_pdf_fails_with_ocr_recovery(client):
    status = upload(client, "scan.pdf", make_pdf(["", ""]))["status"]
    assert status["kind"] == "failed"
    assert status["recovery"] == "ocr"


def test_unsupported_type_fails_with_a_reason(client):
    status = upload(client, "report.docx", b"PK fake docx")["status"]
    assert status["kind"] == "failed"
    assert "isn't supported" in status["reason"]


def test_damaged_pdf_fails_with_a_reason(client):
    status = upload(client, "broken.pdf", b"not really a pdf")["status"]
    assert status == {"kind": "failed", "reason": "This file isn't a valid PDF or is damaged."}


def test_empty_file_fails(client):
    assert upload(client, "empty.txt", b"")["status"] == {"kind": "failed", "reason": "This file is empty."}


def test_file_over_the_size_limit_is_rejected():
    client = TestClient(create_app(Settings(max_upload_bytes=10, _env_file=None)))
    response = client.post("/documents", files={"file": ("big.txt", b"x" * 11)})
    assert response.status_code == 413
    assert "larger than" in response.json()["detail"]


def test_unknown_document_is_404(client):
    response = client.get("/documents/doc_missing")
    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found."}


def test_ocr_reports_it_is_not_available_yet(client):
    created = client.post("/documents", files={"file": ("scan.pdf", make_pdf([""]))}).json()
    response = client.post(f"/documents/{created['id']}/ocr")
    assert response.status_code == 200
    assert response.json()["status"]["kind"] == "failed"
    assert "OCR isn't available" in response.json()["status"]["reason"]


class QuotaExhaustedEmbedder:
    def embed_documents(self, texts):
        raise ProviderRateLimited("The free AI quota is used up for the moment.")

    def embed_query(self, text):
        raise ProviderRateLimited("The free AI quota is used up for the moment.")


def test_provider_quota_error_fails_with_retry(settings):
    app = create_app(settings)
    services = app.state.services
    pipeline = IngestionPipeline(settings, services.registry, QuotaExhaustedEmbedder(), services.store)
    app.state.services = replace(services, pipeline=pipeline)

    status = upload(TestClient(app), "notes.txt", b"Drivers log temperatures every hour.")["status"]
    assert status == {
        "kind": "failed",
        "reason": "The free AI quota is used up for the moment.",
        "recovery": "retry",
    }
