"""
Offline checks for the evaluation in `evals/`: the cases themselves, the
scoring rules, and one small end-to-end run with the stand-in models.
The real run (`uv run python -m evals.run`) needs a Gemini key and never runs in CI.
"""

import pytest

from api.config import Settings
from api.providers import ProviderRateLimited
from api.sales.database import DuckDbSalesDatabase, QueryResult
from api.sales.guard import check_sql
from evals.documents import DOCUMENTS, INJECTION_CANARY
from evals.run import Pacer, Report, build_agent, run_cases, to_markdown
from evals.scoring import declined, facts_present, is_read_only, load_cases, results_match

CASES = load_cases()


def result(columns: list[str], rows: list[tuple[object, ...]]) -> QueryResult:
    return QueryResult(columns, rows, elapsed_ms=0)


# ---------- the cases ----------


@pytest.fixture(scope="module")
def sales_db():
    return DuckDbSalesDatabase()


@pytest.mark.parametrize("case", [c for c in CASES if c.gold_sql], ids=lambda c: c.id)
def test_gold_sql_passes_the_guard_and_returns_rows(case, sales_db):
    for gold in case.gold_sql:
        rows = sales_db.run(check_sql(gold, 200)).rows
        assert rows, f"{case.id}: gold query returned nothing"
        for column in case.label_columns:
            assert column in sales_db.run(check_sql(gold, 200)).columns


@pytest.mark.parametrize("case", [c for c in CASES if c.facts], ids=lambda c: c.id)
def test_every_expected_fact_is_on_the_expected_page(case):
    assert case.file in DOCUMENTS
    page_text = DOCUMENTS[case.file][case.page - 1]
    assert facts_present(page_text, case.facts)


def test_every_case_checks_something():
    for case in CASES:
        assert case.route or case.gold_sql or case.facts or case.decline or case.read_only, case.id


def test_the_injection_case_retrieves_the_page_with_the_hidden_instruction():
    case = next(c for c in CASES if INJECTION_CANARY in c.forbidden)
    assert INJECTION_CANARY in DOCUMENTS[case.file][case.page - 1]


# ---------- scoring rules ----------


def test_extra_columns_and_different_labels_still_match():
    gold = result(["warehouse_id", "late"], [("WH-KT", 41), ("WH-SA", 28)])
    predicted = result(["state", "late_deliveries", "total"], [("Selangor", 28), ("Pahang", 41)])
    predicted = result(predicted.columns, [("Selangor", 28, 900), ("Pahang", 41, 700)])
    assert results_match(gold, predicted, label_columns=["warehouse_id"])


def test_numbers_match_within_rounding():
    gold = result(["sales"], [(458002.8,)])
    assert results_match(gold, result(["total"], [(458002.80,)]))
    assert results_match(gold, result(["total"], [(458003,)]))
    assert not results_match(gold, result(["total"], [(448729.2,)]))


def test_a_different_row_count_fails():
    gold = result(["channel", "n"], [("a", 1), ("b", 2)])
    assert not results_match(gold, result(["channel", "n"], [("a", 1)]), label_columns=["channel"])


def test_first_row_compares_only_the_top_answer():
    gold = result(["sku", "bottles"], [("COC-330", 70572), ("ISO-500", 67500)])
    assert results_match(gold, result(["sku", "bottles"], [("COC-330", 70572)]), ["sku"], "first_row")
    assert not results_match(gold, result(["sku", "bottles"], [("ISO-500", 67500)]), ["sku"], "first_row")


def test_label_only_results_need_one_label_to_match():
    gold = result(["sku", "name"], [("A", "Apple"), ("B", "Banana")])
    assert results_match(gold, result(["product"], [("banana",), ("apple",)]), ["sku", "name"])
    assert not results_match(gold, result(["product"], [("Cherry",), ("Apple",)]), ["sku", "name"])


def test_month_as_timestamp_matches_month_as_date():
    gold = result(["month", "n"], [("2026-01-01", 3)])
    predicted = result(["month", "n"], [("2026-01-01 00:00", 3)])
    assert results_match(gold, predicted)


def test_facts_ignore_citation_markers():
    assert not facts_present("See [2] and [8].", [["2"], ["8"]])
    assert facts_present("Keep it between 2 and 8 degrees [1].", [["2"], ["8"]])


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("I couldn't find this in the files you selected.", True),
        ("I couldn" + chr(0x2019) + "t find this in the files.", True),  # curly apostrophe
        ("The sources do not mention who makes the trucks.", True),
        ("The sales database doesn't hold the information needed for this question.", True),
        ("Penang DC had 9 excursions [1].", False),
        ("Chilled stock must not stay above 8 C for more than 30 minutes [1].", False),
    ],
)
def test_declined(answer, expected):
    assert declined(answer) is expected


def test_read_only():
    assert is_read_only(None)
    assert is_read_only("select 1")
    assert not is_read_only("delete from orders")


# ---------- running ----------


def test_pacer_spaces_calls_and_waits_out_rate_limits():
    waits: list[float] = []
    pacer = Pacer(rpm=60, sleep=waits.append)
    attempts = iter([ProviderRateLimited(retry_after=5), "ok"])

    def flaky() -> str:
        outcome = next(attempts)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    assert pacer.call(flaky) == "ok"
    assert 7 in waits  # retry_after + 2 s margin


def test_end_to_end_with_the_stand_in_models():
    settings = Settings(llm_provider="fake", database_url=None, _env_file=None)
    agent, chat, sales_db, file_ids = build_agent(settings, rpm=0)
    cases = [c for c in CASES if c.id in {"sql-05", "doc-01", "injection-02"}]

    report = run_cases(agent, chat, sales_db, file_ids, cases, Report("fake", "stand-in", "now"), 200)

    passed = {o.id: o.passed for o in report.outcomes}
    assert passed == {"sql-05": True, "doc-01": True, "injection-02": True}
    assert all(o.model_calls >= 1 for o in report.outcomes)
    markdown = to_markdown(report)
    assert "| All cases passed | 3/3 (100%) |" in markdown
    assert "SQL execution accuracy" in markdown
