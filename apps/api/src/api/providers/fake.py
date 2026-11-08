"""
Offline stand-ins for real model providers.

They need no API key and give the same output for the same input, so tests are
fast and repeatable. They are deliberately simple:

- `HashingEmbedder` matches on shared words, not meaning ("car" ≠ "vehicle").
- `ExtractiveChatModel` copies the best-matching sentence from each source
  instead of writing a new answer.

Swap them for a real provider (step 2) to get semantic search and real answers.
"""

import math
import re
import zlib
from collections.abc import Sequence

from api.graph.prompts import QUESTION_LABEL, SOURCE_HEADER_PATTERN, SOURCES_CLOSE, SOURCES_OPEN

_WORD = re.compile(r"\w+", re.UNICODE)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")

# Words too common to say anything about relevance.
_STOPWORD_TEXT = (
    "a an and are as at be by can do does for from has have how i if in is it its of on or "
    "should that the their there these this to was what when where which who why will with you your"
)
STOPWORDS = frozenset(_STOPWORD_TEXT.split())


def tokenize(text: str) -> list[str]:
    return [word for word in _WORD.findall(text.lower()) if word not in STOPWORDS]


class HashingEmbedder:
    """Bag-of-words vector: each word is hashed into one of `dimensions` slots."""

    def __init__(self, dimensions: int = 512) -> None:
        self.dimensions = dimensions

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for word in tokenize(text):
            vector[zlib.crc32(word.encode()) % self.dimensions] += 1.0
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector


class ExtractiveChatModel:
    """Answers by quoting the sentence that best matches the question in each source."""

    max_sources = 2

    def generate(self, system: str, prompt: str) -> str:
        question = _find_question(prompt)
        question_words = set(tokenize(question))

        best: list[tuple[int, int, str]] = []  # (overlap, source index, sentence)
        for index, text in _find_sources(prompt):
            sentences = [s.strip() for s in _SENTENCE_END.split(text) if s.strip()]
            if not sentences:
                continue
            sentence = max(sentences, key=lambda s: len(question_words & set(tokenize(s))))
            overlap = len(question_words & set(tokenize(sentence)))
            if overlap:
                best.append((overlap, index, sentence))

        if not best:
            return "I couldn't find this in the files you selected."

        best.sort(key=lambda item: (-item[0], item[1]))
        chosen = sorted(best[: self.max_sources], key=lambda item: item[1])
        return " ".join(f"{_ensure_period(sentence)} [{index}]" for _, index, sentence in chosen)


def _find_question(prompt: str) -> str:
    for line in prompt.splitlines():
        if line.startswith(QUESTION_LABEL):
            return line.removeprefix(QUESTION_LABEL).strip()
    return ""


def _find_sources(prompt: str) -> list[tuple[int, str]]:
    """Splits the prompt's source blocks into (citation number, text) pairs."""
    start, end = prompt.find(SOURCES_OPEN), prompt.find(SOURCES_CLOSE)
    if start == -1 or end == -1:
        return []
    parts = SOURCE_HEADER_PATTERN.split(prompt[start + len(SOURCES_OPEN) : end])
    # re.split with one capture group gives [before, n1, text1, n2, text2, ...]
    return [(int(parts[i]), parts[i + 1].strip()) for i in range(1, len(parts) - 1, 2)]


def _ensure_period(sentence: str) -> str:
    return sentence if sentence.endswith((".", "!", "?")) else f"{sentence}."
