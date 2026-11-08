"""
Splits page text into overlapping chunks for retrieval.

Each chunk stays within one page, so a citation can always say which page it
came from. Chunks end at a sentence or line break where possible, and the
overlap keeps a sentence that straddles a boundary findable from either side.
"""

import re
from dataclasses import dataclass

_SPACES = re.compile(r"[ \t\f\v]+")
_BLANK_LINES = re.compile(r"\n{3,}")


@dataclass(frozen=True)
class PageChunk:
    text: str
    page: int  # 1-based


def normalize(text: str) -> str:
    """Collapses runs of spaces and blank lines that PDF extraction leaves behind."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [_SPACES.sub(" ", line).strip() for line in text.split("\n")]
    return _BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()


def split_text(text: str, size: int, overlap: int) -> list[str]:
    if overlap >= size:
        raise ValueError("overlap must be smaller than size")
    text = normalize(text)
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            end = _best_break(text, start, end)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = _next_word_start(text, max(end - overlap, start + 1), end)
    return chunks


def chunk_pages(pages: list[str], size: int, overlap: int) -> list[PageChunk]:
    return [
        PageChunk(text=chunk, page=number)
        for number, page_text in enumerate(pages, start=1)
        for chunk in split_text(page_text, size, overlap)
    ]


def _best_break(text: str, start: int, end: int) -> int:
    """Moves `end` back to the last paragraph, sentence or word break, if one is reasonably close."""
    floor = start + (end - start) // 2
    for separator in ("\n\n", ". ", "\n", " "):
        cut = text.rfind(separator, floor, end)
        if cut != -1:
            return cut + len(separator)
    return end


def _next_word_start(text: str, position: int, limit: int) -> int:
    """Avoids starting a chunk in the middle of a word."""
    while position < limit and not text[position - 1].isspace():
        position += 1
    return position
