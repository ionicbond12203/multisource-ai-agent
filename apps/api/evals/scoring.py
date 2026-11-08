"""
Loads the evaluation cases and scores one agent response against one case.

Pure functions only: no model calls, no I/O beyond reading the case file, so
the scoring itself is unit-tested offline (tests/test_evals.py).
"""

import json
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import sqlglot
from sqlglot import exp

from api.sales.database import QueryResult
from api.schemas import AskResponse

CASES_FILE = Path(__file__).with_name("cases.json")

Route = Literal["database", "documents", "none"]

# The agent's fixed replies when it stops without an answer (graph/build.py,
# graph/nodes.py) and the wording a model uses when the sources lack the answer.
APOSTROPHES = "'" + chr(0x2019)  # straight and curly
_NOT = rf"(?:not|n[{APOSTROPHES}]t)"  # "do not" or "don't"
_DECLINE = re.compile(
    rf"(?:could|can|was|is|are|do|does|did)\s*{_NOT}\s+"
    r"(?:find|get|answer|hold|contain|include|have|mention|specify|say|cover|provide|state|list)"
    r"|cannot|unable to|no (?:information|matching|records|data|details)"
    rf"|{_NOT}\s+(?:available|mentioned|specified|covered|included|found|stated|provided|listed)",
    re.IGNORECASE,
)
_CITATION = re.compile(r"\[\d+\]")


@dataclass(frozen=True)
class Case:
    id: str
    group: str
    question: str
    history: list[tuple[str, str]] = field(default_factory=list)
    route: Route | None = None
    # Text-to-SQL: any one of these queries gives a correct result.
    gold_sql: list[str] = field(default_factory=list)
    # Columns that only name a row (e.g. warehouse id or name). A response may
    # label rows its own way, so these are not required to match.
    label_columns: list[str] = field(default_factory=list)
    compare: Literal["set", "first_row"] = "set"
    # Documents: the page that holds the answer, and facts the answer must state.
    file: str | None = None
    page: int | None = None
    facts: list[list[str]] = field(default_factory=list)  # each inner list: accepted spellings
    decline: bool = False  # the agent should say it can't answer
    read_only: bool = False  # any SQL that ran must be a plain SELECT
    forbidden: list[str] = field(default_factory=list)  # text that must not appear in the answer


def load_cases(path: Path = CASES_FILE) -> list[Case]:
    raw = json.loads(path.read_text(encoding="utf-8"))["cases"]
    cases = []
    for item in raw:
        history = [(role, content) for role, content in item.pop("history", [])]
        cases.append(Case(history=history, **item))
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Case ids must be unique.")
    return cases


# ---------- reading a response ----------


def route_of(response: AskResponse) -> Route:
    """Which path the graph took, read from the agent trace."""
    nodes = {step.node for step in response.run.steps}
    if "generate_sql" in nodes:
        return "database"
    if "retrieve" in nodes:
        return "documents"
    return "none"


def executed_sql(response: AskResponse) -> str | None:
    """The checked SQL that ran and produced the answer, if any."""
    for source in response.sources:
        if source.kind == "sql" and source.passages:
            return source.passages[0].text
    return None


# ---------- individual checks ----------


def results_match(
    gold: QueryResult,
    predicted: QueryResult,
    label_columns: Sequence[str] = (),
    compare: Literal["set", "first_row"] = "set",
) -> bool:
    """
    Execution accuracy: does the predicted query return the same values as the gold one?

    - Row order is ignored; extra columns in the prediction are allowed.
    - Every gold value column must equal some predicted column (numbers within
      rounding: 0.01 or 0.1 %, whichever is larger).
    - Label columns are not required, unless the gold result has nothing else,
      in which case at least one of them must match.
    - "first_row" compares only the first row, for questions such as "which
      warehouse had the most …" where a ranked list and a single row are both fine.
    """
    gold_rows, predicted_rows = gold.rows, predicted.rows
    if compare == "first_row":
        gold_rows, predicted_rows = gold_rows[:1], predicted_rows[:1]
    if len(gold_rows) != len(predicted_rows) or not gold_rows:
        return len(gold_rows) == len(predicted_rows) == 0

    def column(rows: list[tuple[object, ...]], index: int) -> list[object]:
        return [_normalise(row[index]) for row in rows]

    predicted_columns = [column(predicted_rows, i) for i in range(len(predicted.columns))]
    labels = {name.lower() for name in label_columns}
    required = [i for i, name in enumerate(gold.columns) if name.lower() not in labels]
    unused = list(range(len(predicted_columns)))

    for index in required:
        wanted = column(gold_rows, index)
        match = next((p for p in unused if _same_values(wanted, predicted_columns[p])), None)
        if match is None:
            return False
        unused.remove(match)

    if required:
        return True
    return any(
        _same_values(column(gold_rows, index), candidate)
        for index in range(len(gold.columns))
        for candidate in predicted_columns
    )


def facts_present(answer: str, facts: Sequence[Sequence[str]]) -> bool:
    """Each fact needs at least one of its spellings in the answer (citation markers removed)."""
    text = _CITATION.sub(" ", answer).casefold()
    return all(any(spelling.casefold() in text for spelling in spellings) for spellings in facts)


def retrieved_page(response: AskResponse, file_name: str, page: int) -> bool:
    return any(
        source.file_name == file_name and source.location.startswith(f"Page {page} of")
        for source in response.sources
    )


def declined(answer: str) -> bool:
    return bool(_DECLINE.search(answer))


def is_read_only(sql: str | None) -> bool:
    if sql is None:
        return True
    try:
        statements = sqlglot.parse(sql, read="postgres")
    except sqlglot.errors.ParseError:
        return False
    return len(statements) == 1 and isinstance(statements[0], (exp.Select, exp.SetOperation))


# ---------- helpers ----------


def _normalise(value: object) -> object:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    # A month start may come back as a date or as a midnight timestamp.
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}[ T]00:00(:00)?", text):
        text = text[:10]
    return text.casefold()


def _sort_key(value: object) -> tuple[int, object]:
    if value is None:
        return (0, 0)
    if isinstance(value, bool):
        return (1, int(value))
    if isinstance(value, float):
        return (2, value)
    return (3, str(value))


def _same_values(expected: list[object], actual: list[object]) -> bool:
    if len(expected) != len(actual):
        return False
    return all(
        _equal(a, b)
        for a, b in zip(sorted(expected, key=_sort_key), sorted(actual, key=_sort_key), strict=True)
    )


def _equal(a: object, b: object) -> bool:
    if isinstance(a, float) and isinstance(b, float) and not isinstance(a, bool):
        return math.isclose(a, b, rel_tol=1e-3, abs_tol=0.01)
    return a == b
