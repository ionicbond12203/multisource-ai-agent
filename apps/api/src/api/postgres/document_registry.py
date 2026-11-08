"""Postgres implementation of `DocumentRegistry`."""

from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool
from pydantic import TypeAdapter

from api.ingestion.registry import DocumentNotFound, DocumentRecord, new_document_id
from api.schemas import Failed, FileStatus

_status = TypeAdapter(FileStatus)

INTERRUPTED = Failed(reason="Processing was interrupted when the server restarted. Upload the file again.")


class PostgresDocumentRegistry:
    def __init__(self, pool: ConnectionPool) -> None:
        self.pool = pool

    def create(self, name: str, status: FileStatus) -> DocumentRecord:
        record = DocumentRecord(id=new_document_id(), name=name, status=status)
        with self.pool.connection() as connection:
            connection.execute(
                "insert into documents (id, name, status) values (%s, %s, %s)",
                (record.id, record.name, _to_json(status)),
            )
        return record

    def get(self, document_id: str) -> DocumentRecord:
        with self.pool.connection() as connection:
            row = connection.execute(
                "select id, name, status from documents where id = %s", (document_id,)
            ).fetchone()
        if row is None:
            raise DocumentNotFound(document_id)
        return DocumentRecord(id=row[0], name=row[1], status=_status.validate_python(row[2]))

    def set_status(self, document_id: str, status: FileStatus) -> DocumentRecord:
        with self.pool.connection() as connection:
            row = connection.execute(
                "update documents set status = %s, updated_at = now() where id = %s returning name",
                (_to_json(status), document_id),
            ).fetchone()
        if row is None:
            raise DocumentNotFound(document_id)
        return DocumentRecord(id=document_id, name=row[0], status=status)

    def fail_interrupted(self) -> int:
        """
        Marks documents still "uploading" or "processing" as failed.

        Processing runs inside the server process, so if the server restarts
        (free hosts sleep and wake), unfinished documents would otherwise show
        "processing" forever. Call this at startup. Returns how many were fixed.
        """
        with self.pool.connection() as connection:
            cursor = connection.execute(
                "update documents set status = %s, updated_at = now() "
                "where status->>'kind' in ('uploading', 'processing')",
                (_to_json(INTERRUPTED),),
            )
            # Their partial chunks are useless, so remove them too.
            connection.execute(
                "delete from chunks where document_id in "
                "(select id from documents where status->>'reason' = %s)",
                (INTERRUPTED.reason,),
            )
            return cursor.rowcount


def _to_json(status: FileStatus) -> Jsonb:
    return Jsonb(_status.dump_python(status, mode="json", by_alias=True, exclude_none=True))
