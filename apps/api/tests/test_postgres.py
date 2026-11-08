"""
Postgres + pgvector tests. Skipped unless TEST_DATABASE_URL points at a
database you don't mind being written to (CI starts a throwaway one):

    docker compose up -d db
    TEST_DATABASE_URL=postgresql://postgres@localhost:5432/postgres uv run pytest

Never point this at the Supabase project the demo uses.
"""

import os

import pytest
from fastapi.testclient import TestClient
from helpers import upload
from pdf_factory import make_pdf

from api.config import Settings
from api.ingestion.registry import DocumentNotFound
from api.main import create_app
from api.postgres import create_pool
from api.postgres.document_registry import INTERRUPTED, PostgresDocumentRegistry
from api.postgres.vector_store import PostgresVectorStore
from api.schemas import Processing, Ready
from api.store.base import Chunk

DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="set TEST_DATABASE_URL to run Postgres tests")


@pytest.fixture
def pool():
    pool = create_pool(DATABASE_URL)
    with pool.connection() as connection:
        connection.execute("truncate documents cascade")
    yield pool
    pool.close()


def unit(*values: float) -> list[float]:
    """A 768-dim vector with the given leading values."""
    return list(values) + [0.0] * (768 - len(values))


def test_registry_round_trip(pool):
    registry = PostgresDocumentRegistry(pool)
    record = registry.create("a.pdf", Processing(stage="parsing"))
    assert registry.get(record.id).status == Processing(stage="parsing")

    registry.set_status(record.id, Ready(pages=3, chunks=7))
    assert registry.get(record.id).status == Ready(pages=3, chunks=7)

    with pytest.raises(DocumentNotFound):
        registry.get("doc_missing")


def test_interrupted_documents_are_marked_failed(pool):
    registry = PostgresDocumentRegistry(pool)
    stuck = registry.create("stuck.pdf", Processing(stage="embedding"))
    done = registry.create("done.pdf", Ready(pages=1, chunks=1))

    assert registry.fail_interrupted() == 1
    assert registry.get(stuck.id).status == INTERRUPTED
    assert registry.get(done.id).status == Ready(pages=1, chunks=1)


def test_vector_search_filters_by_file_and_ranks_by_similarity(pool):
    registry = PostgresDocumentRegistry(pool)
    first = registry.create("first.pdf", Ready(pages=1, chunks=2)).id
    second = registry.create("second.pdf", Ready(pages=1, chunks=1)).id
    store = PostgresVectorStore(pool)
    store.add(
        [
            Chunk(f"{first}:0", first, "first.pdf", "close match", 1, 1),
            Chunk(f"{first}:1", first, "first.pdf", "weak match", 1, 1),
            Chunk(f"{second}:0", second, "second.pdf", "other file", 1, 1),
        ],
        [unit(1.0), unit(0.6, 0.8), unit(1.0)],
    )

    results = store.search(unit(1.0), [first], top_k=5)
    assert [r.chunk.text for r in results] == ["close match", "weak match"]
    assert results[0].score == pytest.approx(1.0)
    assert results[1].score == pytest.approx(0.6)

    store.delete_file(first)
    assert store.search(unit(1.0), [first], top_k=5) == []
    assert store.search(unit(1.0), [], top_k=5) == []


def test_full_flow_through_the_api():
    app = create_app(Settings(database_url=DATABASE_URL, chunk_size=300, chunk_overlap=50, _env_file=None))
    with TestClient(app) as client:  # `with` runs startup and shutdown, which closes the pool
        pdf = make_pdf(["Intro page.", "Chilled RTD tea must be kept between 2 C and 8 C."])
        document = upload(client, "sop.pdf", pdf)
        assert document["status"]["kind"] == "ready"

        body = client.post(
            "/chat",
            json={
                "question": "What temperature for chilled RTD tea?",
                "fileIds": [document["id"]],
                "history": [],
            },
        ).json()
        assert body["grounded"] is True
        assert body["sources"][0]["location"] == "Page 2 of 2"
