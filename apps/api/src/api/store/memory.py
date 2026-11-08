"""
In-memory vector store.

Fine for local development and tests. Everything is lost when the process
restarts; step 2 replaces it with Postgres + pgvector.
"""

import math
import threading
from collections.abc import Collection, Sequence

from api.store.base import Chunk, ScoredChunk


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._rows: list[tuple[Chunk, list[float]]] = []
        self._lock = threading.Lock()

    def add(self, chunks: Sequence[Chunk], vectors: Sequence[Sequence[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        with self._lock:
            self._rows.extend((chunk, list(vector)) for chunk, vector in zip(chunks, vectors, strict=True))

    def search(self, vector: Sequence[float], file_ids: Collection[str], top_k: int) -> list[ScoredChunk]:
        wanted = set(file_ids)
        with self._lock:
            candidates = [(chunk, stored) for chunk, stored in self._rows if chunk.file_id in wanted]
        scored = [ScoredChunk(chunk, _cosine(vector, stored)) for chunk, stored in candidates]
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]

    def delete_file(self, file_id: str) -> None:
        with self._lock:
            self._rows = [row for row in self._rows if row[0].file_id != file_id]


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    # Clamp: floating-point error can push the result slightly outside 0 to 1.
    return max(0.0, min(1.0, dot / norm)) if norm else 0.0
