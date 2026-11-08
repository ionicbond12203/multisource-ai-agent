"""
Keeps track of uploaded documents and their processing status.

The frontend polls GET /documents/{id} and shows whatever status is stored
here. In-memory for now; step 2 moves it to Postgres so it survives restarts.
"""

import threading
import uuid
from dataclasses import dataclass, replace

from api.schemas import FileStatus


@dataclass(frozen=True)
class DocumentRecord:
    id: str
    name: str
    status: FileStatus


class DocumentNotFound(KeyError):
    pass


class DocumentRegistry:
    def __init__(self) -> None:
        self._records: dict[str, DocumentRecord] = {}
        self._lock = threading.Lock()

    def create(self, name: str, status: FileStatus) -> DocumentRecord:
        record = DocumentRecord(id=f"doc_{uuid.uuid4().hex[:12]}", name=name, status=status)
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
