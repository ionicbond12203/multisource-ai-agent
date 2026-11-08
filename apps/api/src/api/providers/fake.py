"""
Offline stand-ins for real model providers.

They need no API key and give the same output for the same input, so tests are
fast and repeatable. They are deliberately simple:

- `HashingEmbedder` matches on shared words, not meaning ("car" ≠ "vehicle").
- `ExtractiveChatModel` copies the best-matching sentence from each source
  instead of writing a new answer, and rewrites follow-ups by prepending the
  previous user question. For the sales database it routes on keywords, knows
  a handful of fixed queries, and summarises the first result row.

Set LLM_PROVIDER=gemini for semantic search and real answers.
"""

import math
import re
import zlib
from collections.abc import Sequence

from api.graph.prompts import (
    CANNOT_ANSWER,
    DATA_ANSWER_SYSTEM_PROMPT,
    FOLLOW_UP_LABEL,
    PREVIOUS_QUESTION_LABEL,
    QUESTION_LABEL,
    REWRITE_SYSTEM_PROMPT,
    ROUTER_SYSTEM_PROMPT,
    SOURCE_HEADER_PATTERN,
    SOURCES_CLOSE,
    SOURCES_OPEN,
    SQL_SYSTEM_PROMPT,
)

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

    def __init__(self, dimensions: int = 768) -> None:
        self.dimensions = dimensions

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_one(text)

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
        if system == ROUTER_SYSTEM_PROMPT:
            return _route(prompt)
        if system == REWRITE_SYSTEM_PROMPT:
            return _rewrite(prompt)
        if system == SQL_SYSTEM_PROMPT:
            return _write_sql(prompt)
        if system == DATA_ANSWER_SYSTEM_PROMPT:
            return _summarise_result(prompt)
        return self._answer(prompt)

    def _answer(self, prompt: str) -> str:
        question = _find_line(prompt, QUESTION_LABEL)
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


# ---------- sales database ----------

# Phrases that suggest a question about numbers in the sales data.
_DATA_PHRASES = (
    "how many", "how much", "total", "average", "count", "top ", "most ", "highest", "lowest",
    "per month", "by month", "trend", "revenue", "sales", "late deliveries", "excursions", "q1", "q2", "q3",
)  # fmt: skip

_LATE_BY_STATE = """
select w.state, count(*) filter (where d.delivered_at::date > d.promised_date) as late_deliveries,
       count(*) as deliveries
from deliveries d join orders o on o.id = d.order_id join warehouses w on w.id = o.warehouse_id
where o.status <> 'cancelled'{quarter}
group by w.state order by late_deliveries desc"""

_EXCURSIONS_BY_WAREHOUSE = """
select o.warehouse_id, count(*) as excursions
from deliveries d join orders o on o.id = d.order_id
where d.temperature_excursion{quarter}
group by o.warehouse_id order by excursions desc"""

_TOP_CUSTOMERS = """
select c.name, round(sum(i.quantity * i.unit_price_myr), 2) as sales_myr
from orders o join order_items i on i.order_id = o.id join customers c on c.id = o.customer_id
where o.status = 'delivered'{quarter}
group by c.name order by sales_myr desc limit 5"""

_SALES_BY_MONTH = """
select date_trunc('month', o.order_date)::date as month, round(sum(i.quantity * i.unit_price_myr), 2) as sales_myr
from orders o join order_items i on i.order_id = o.id
where o.status = 'delivered'{quarter}
group by 1 order by 1"""


def _route(prompt: str) -> str:
    question = _find_line(prompt, QUESTION_LABEL).lower()
    return "database" if any(phrase in question for phrase in _DATA_PHRASES) else "documents"


def _write_sql(prompt: str) -> str:
    question = _find_line(prompt, QUESTION_LABEL).lower()
    quarter_match = re.search(r"q([1-4])", question)
    quarter = f" and extract(quarter from o.order_date) = {quarter_match.group(1)}" if quarter_match else ""
    if "late" in question:
        template = _LATE_BY_STATE
    elif "excursion" in question:
        template = _EXCURSIONS_BY_WAREHOUSE
    elif "customer" in question:
        template = _TOP_CUSTOMERS
    elif "sales" in question or "revenue" in question:
        template = _SALES_BY_MONTH
    else:
        return CANNOT_ANSWER
    return template.format(quarter=quarter).strip()


def _summarise_result(prompt: str) -> str:
    sources = _find_sources(prompt)
    if not sources:
        return "No matching records were found."
    lines = sources[0][1].split("Result:", 1)[-1].strip().splitlines()
    if not lines or lines[0].startswith("no rows"):
        return "No matching records were found [1]."
    if len(lines) < 3:
        return f"The query returned {lines[0]} [1]."
    columns, first = lines[1].split(" | "), lines[2].split(" | ")
    top = ", ".join(f"{column} = {value}" for column, value in zip(columns, first, strict=False))
    return f"The query returned {lines[0]}. The first row is {top} [1]."


def _rewrite(prompt: str) -> str:
    """Joins the previous user question and the follow-up, so shared words still match."""
    previous = _find_line(prompt, PREVIOUS_QUESTION_LABEL)
    follow_up = _find_line(prompt, FOLLOW_UP_LABEL)
    return f"{previous} {follow_up}".strip()


def _find_line(prompt: str, label: str) -> str:
    for line in prompt.splitlines():
        if line.startswith(label):
            return line.removeprefix(label).strip()
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
