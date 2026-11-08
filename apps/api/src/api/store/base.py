"""Vector store interface and the records it holds."""

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Chunk:
    """One searchable piece of a document."""

    id: str
    file_id: str
    file_name: str
    text: str
    page: int  # 1-based
    page_count: int


@dataclass(frozen=True)
class ScoredChunk:
    chunk: Chunk
    score: float  # cosine similarity, 0 to 1


class VectorStore(Protocol):
    def add(self, chunks: Sequence[Chunk], vectors: Sequence[Sequence[float]]) -> None: ...

    def search(self, vector: Sequence[float], file_ids: Collection[str], top_k: int) -> list[ScoredChunk]:
        """Best matches among the given files, highest score first."""
        ...

    def delete_file(self, file_id: str) -> None: ...
