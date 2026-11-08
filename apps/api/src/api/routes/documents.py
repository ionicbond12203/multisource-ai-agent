"""
Document upload and status endpoints.

    POST /documents            multipart field "file"  → DocumentResponse (201)
    GET  /documents/{id}                               → DocumentResponse
    POST /documents/{id}/ocr                           → DocumentResponse
"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status

from api.ingestion.extract import SUPPORTED_EXTENSIONS, extension_of
from api.ingestion.registry import DocumentNotFound, DocumentRecord
from api.schemas import DocumentResponse, Failed, Processing
from api.services import Services, get_services

router = APIRouter(prefix="/documents", tags=["documents"])

ServicesDep = Annotated[Services, Depends(get_services)]
READ_BLOCK_BYTES = 1024 * 1024


@router.post("", status_code=status.HTTP_201_CREATED, response_model_exclude_none=True)
async def upload_document(
    file: Annotated[UploadFile, File()], services: ServicesDep, background: BackgroundTasks
) -> DocumentResponse:
    name = file.filename or "untitled"
    data = await _read_limited(file, services.settings.max_upload_bytes)

    # Problems we can spot right away still create a record, so the frontend
    # shows the reason on the file row instead of a generic upload error.
    if extension_of(name) not in SUPPORTED_EXTENSIONS:
        reason = f"This file type isn't supported yet. Upload a {', '.join(SUPPORTED_EXTENSIONS)} file."
        return _response(services.registry.create(name, Failed(reason=reason)))
    if not data:
        return _response(services.registry.create(name, Failed(reason="This file is empty.")))

    record = services.registry.create(name, Processing(stage="parsing"))
    background.add_task(services.pipeline.run, record.id, name, data)
    return _response(record)


@router.get("/{document_id}", response_model_exclude_none=True)
def get_document(document_id: str, services: ServicesDep) -> DocumentResponse:
    return _response(_find(services, document_id))


@router.post("/{document_id}/ocr", response_model_exclude_none=True)
def run_ocr(document_id: str, services: ServicesDep) -> DocumentResponse:
    _find(services, document_id)
    # OCR (reading text from scanned images) is not built yet. Say so clearly
    # rather than pretending to retry.
    record = services.registry.set_status(
        document_id, Failed(reason="OCR isn't available in this demo yet. Upload a PDF with selectable text.")
    )
    return _response(record)


def _find(services: Services, document_id: str) -> DocumentRecord:
    try:
        return services.registry.get(document_id)
    except DocumentNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found.") from None


async def _read_limited(file: UploadFile, max_bytes: int) -> bytes:
    """Reads the upload, stopping as soon as it goes over the size limit."""
    data = bytearray()
    while block := await file.read(READ_BLOCK_BYTES):
        data.extend(block)
        if len(data) > max_bytes:
            raise HTTPException(
                status.HTTP_413_CONTENT_TOO_LARGE,
                f"File is larger than {max_bytes // (1024 * 1024)} MB.",
            )
    return bytes(data)


def _response(record: DocumentRecord) -> DocumentResponse:
    return DocumentResponse(id=record.id, status=record.status)
