"""pgvector implementation of `VectorStore`."""

from collections.abc import Collection, Sequence

from pgvector import Vector
from psycopg_pool import ConnectionPool

from api.store.base import Chunk, ScoredChunk


class PostgresVectorStore:
    def __init__(self, pool: ConnectionPool) -> None:
        self.pool = pool

    def add(self, chunks: Sequence[Chunk], vectors: Sequence[Sequence[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must have the same length")
        rows = [
            (c.id, c.file_id, c.file_name, c.text, c.page, c.page_count, Vector(list(v)))
            for c, v in zip(chunks, vectors, strict=True)
        ]
        with self.pool.connection() as connection, connection.cursor() as cursor:
            cursor.executemany(
                "insert into chunks (id, document_id, file_name, text, page, page_count, embedding) "
                "values (%s, %s, %s, %s, %s, %s, %s) on conflict (id) do nothing",
                rows,
            )

    def search(self, vector: Sequence[float], file_ids: Collection[str], top_k: int) -> list[ScoredChunk]:
        if not file_ids:
            return []
        query = Vector(list(vector))
        with self.pool.connection() as connection:
            rows = connection.execute(
                # `<=>` is cosine distance (0 = same direction, 2 = opposite).
                "select id, document_id, file_name, text, page, page_count, embedding <=> %s as distance "
                "from chunks where document_id = any(%s) order by distance limit %s",
                (query, list(file_ids), top_k),
            ).fetchall()
        return [
            ScoredChunk(
                Chunk(id=r[0], file_id=r[1], file_name=r[2], text=r[3], page=r[4], page_count=r[5]),
                score=max(0.0, min(1.0, 1 - float(r[6]))),
            )
            for r in rows
        ]

    def delete_file(self, file_id: str) -> None:
        with self.pool.connection() as connection:
            connection.execute("delete from chunks where document_id = %s", (file_id,))
