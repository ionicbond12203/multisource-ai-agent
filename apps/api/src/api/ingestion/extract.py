"""Reads the text out of an uploaded file, one string per page."""

import io
import logging
from pathlib import PurePath

from pypdf import PdfReader
from pypdf.errors import PdfReadError

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = (".pdf", ".txt", ".md")


class ExtractionError(Exception):
    """The file can't be read. The message is shown to the user."""


def extension_of(file_name: str) -> str:
    return PurePath(file_name).suffix.lower()


def extract_pages(file_name: str, data: bytes) -> list[str]:
    extension = extension_of(file_name)
    if extension == ".pdf":
        return _extract_pdf(data)
    if extension in (".txt", ".md"):
        # Plain text has no pages; treat the whole file as page 1.
        return [data.decode("utf-8", errors="replace")]
    raise ExtractionError(
        f"{extension or 'This'} files aren't supported yet. Upload a {', '.join(SUPPORTED_EXTENSIONS)} file."
    )


def _extract_pdf(data: bytes) -> list[str]:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ExtractionError("This PDF is password-protected. Remove the password and upload it again.")
        return [page.extract_text() or "" for page in reader.pages]
    except PdfReadError as error:
        logger.info("Unreadable PDF: %s", error)
        raise ExtractionError("This file isn't a valid PDF or is damaged.") from error
