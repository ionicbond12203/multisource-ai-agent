"""
Keeps track of uploaded documents and their processing status.

The frontend polls GET /documents/{id} and shows whatever status is stored
here. `InMemoryDocumentRegistry` is used without a database;
`api.postgres.document_registry` stores the same records in Postgres.
"""

import threading
import uuid
from dataclasses import dataclass, replace
from typing import Protocol

from api.schemas import FileStatus


@dataclass(frozen=True)
class DocumentRecord:
    id: str
    name: str
    status: FileStatus


class DocumentNotFound(KeyError):
    pass


class DocumentRegistry(Protocol):
    def create(self, name: str, status: FileStatus) -> DocumentRecord: ...

    def get(self, document_id: str) -> DocumentRecord:
        """Raises DocumentNotFound."""
        ...

    def set_status(self, document_id: str, status: FileStatus) -> DocumentRecord:
        """Raises DocumentNotFound."""
        ...


def new_document_id() -> str:
    return f"doc_{uuid.uuid4().hex[:12]}"


class InMemoryDocumentRegistry:
    def __init__(self) -> None:
        self._records: dict[str, DocumentRecord] = {}
        self._lock = threading.Lock()

    def create(self, name: str, status: FileStatus) -> DocumentRecord:
        record = DocumentRecord(id=new_document_id(), name=name, status=status)
        with self._lock:
            self._records[record.id] = record
        return record

    def get(self, document_id: str) -> DocumentRecord:
        with self._lock:
            record = self._records.get(document_id)
        if record is None:
            raise DocumentNotFound(document_id)
        return record

    def set_status(self, document_id: str, status: FileStatus) -> DocumentRecord:
        with self._lock:
            record = self._records.get(document_id)
            if record is None:
                raise DocumentNotFound(document_id)
            record = replace(record, status=status)
            self._records[document_id] = record
        return record
