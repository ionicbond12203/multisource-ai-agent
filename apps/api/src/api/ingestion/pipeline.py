"""
Turns an uploaded file into searchable chunks:

    parsing → chunking → embedding → indexing → ready

Runs in the background after POST /documents returns. Each stage writes its
status to the registry so the frontend can show progress. Any failure ends in
a `Failed` status with a reason the user can act on, never a silent hang.
"""

import logging
from collections.abc import Sequence

from api.config import Settings
from api.ingestion.chunking import chunk_pages
from api.ingestion.extract import ExtractionError, extract_pages
from api.ingestion.registry import DocumentRegistry
from api.providers.base import Embedder, ProviderError
from api.schemas import Failed, Processing, Ready
from api.store.base import Chunk, VectorStore

logger = logging.getLogger(__name__)

EMBED_BATCH_SIZE = 32
# Fewer extracted characters per page than this means there's no real text layer.
MIN_CHARS_PER_PAGE = 20


class IngestionPipeline:
    def __init__(
        self, settings: Settings, registry: DocumentRegistry, embedder: Embedder, store: VectorStore
    ) -> None:
        self.settings = settings
        self.registry = registry
        self.embedder = embedder
        self.store = store

    def run(self, document_id: str, file_name: str, data: bytes) -> None:
        try:
            self._run(document_id, file_name, data)
        except ExtractionError as error:
            self.registry.set_status(document_id, Failed(reason=str(error)))
        except ProviderError as error:
            self.store.delete_file(document_id)
            self.registry.set_status(document_id, Failed(reason=str(error), recovery="retry"))
        except Exception:
            logger.exception("Ingestion failed for %s", document_id)
            self.store.delete_file(document_id)
            self.registry.set_status(
                document_id, Failed(reason="Processing failed unexpectedly. Try again.", recovery="retry")
            )

    def _run(self, document_id: str, file_name: str, data: bytes) -> None:
        set_status = self.registry.set_status

        set_status(document_id, Processing(stage="parsing"))
        pages = extract_pages(file_name, data)
        if len(pages) > self.settings.max_pages:
            limit = self.settings.max_pages
            raise ExtractionError(f"This file has {len(pages)} pages. The limit is {limit}.")
        if sum(len(page.strip()) for page in pages) < MIN_CHARS_PER_PAGE * max(len(pages), 1):
            set_status(
                document_id,
                Failed(reason="No text found. This looks like a scanned document.", recovery="ocr"),
            )
            return

        set_status(document_id, Processing(stage="chunking"))
        page_chunks = chunk_pages(pages, self.settings.chunk_size, self.settings.chunk_overlap)
        chunks = [
            Chunk(
                id=f"{document_id}:{number}",
                file_id=document_id,
                file_name=file_name,
                text=page_chunk.text,
                page=page_chunk.page,
                page_count=len(pages),
            )
            for number, page_chunk in enumerate(page_chunks)
        ]

        vectors = self._embed(document_id, [chunk.text for chunk in chunks])

        set_status(document_id, Processing(stage="indexing"))
        self.store.add(chunks, vectors)

        set_status(document_id, Ready(pages=len(pages), chunks=len(chunks)))

    def _embed(self, document_id: str, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), EMBED_BATCH_SIZE):
            self.registry.set_status(
                document_id, Processing(stage="embedding", progress=start / max(len(texts), 1))
            )
            vectors.extend(self.embedder.embed_documents(texts[start : start + EMBED_BATCH_SIZE]))
        return vectors
