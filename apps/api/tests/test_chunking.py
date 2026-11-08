import itertools

import pytest

from api.ingestion.chunking import chunk_pages, normalize, split_text

LONG_TEXT = " ".join(f"Sentence number {n} talks about cold chain storage." for n in range(60))


def test_normalize_collapses_whitespace():
    assert normalize("a   b\t c\r\n\n\n\nd ") == "a b c\n\nd"


def test_chunks_respect_the_size_limit():
    chunks = split_text(LONG_TEXT, size=300, overlap=50)
    assert len(chunks) > 1
    assert all(len(chunk) <= 300 for chunk in chunks)


def test_chunks_cover_the_whole_text():
    chunks = split_text(LONG_TEXT, size=300, overlap=50)
    assert chunks[0].startswith("Sentence number 0 ")
    assert chunks[-1].endswith("Sentence number 59 talks about cold chain storage.")


def test_chunks_overlap_and_never_start_mid_word():
    chunks = split_text(LONG_TEXT, size=300, overlap=50)
    for previous, current in itertools.pairwise(chunks):
        first_word = current.split()[0]
        assert first_word in previous  # overlap carries text across the boundary
        assert f" {first_word}" in f" {LONG_TEXT}"  # starts on a word boundary


def test_short_text_is_one_chunk():
    assert split_text("Short note.", size=300, overlap=50) == ["Short note."]


def test_empty_pages_give_no_chunks_and_pages_are_numbered():
    chunks = chunk_pages(["First page text.", "", "Third page text."], size=300, overlap=50)
    assert [(chunk.page, chunk.text) for chunk in chunks] == [
        (1, "First page text."),
        (3, "Third page text."),
    ]


def test_overlap_must_be_smaller_than_size():
    with pytest.raises(ValueError):
        split_text("text", size=100, overlap=100)
