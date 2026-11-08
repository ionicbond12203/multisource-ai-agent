"""
Runs every evaluation case through the real chat agent and writes a report.

    cd apps/api
    uv run python -m evals.run                   # uses LLM_PROVIDER from .env
    uv run python -m evals.run --provider fake   # offline, no key (checks the harness, not the model)
    uv run python -m evals.run --only sql-03 doc-02

The agent runs exactly as in production (same graph, prompts, SQL guard and
citation check), with two differences so a run is repeatable and never touches
the live demo: documents are kept in memory, and the sales data comes from the
embedded DuckDB copy (the same deterministic rows as Supabase).

Gemini's free tier allows 15 requests a minute, so model calls are spaced out
(--rpm) and a rate-limit reply waits and retries. A full run takes ~10 minutes.
"""

import argparse
import json
import statistics
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from api.config import Settings
from api.graph.build import ChatAgent
from api.ingestion.pipeline import IngestionPipeline
from api.ingestion.registry import InMemoryDocumentRegistry
from api.providers import ProviderError, ProviderRateLimited, build_providers
from api.providers.base import ChatModel, Embedder
from api.sales.database import DuckDbSalesDatabase, QueryFailed, QueryResult, SalesDatabase
from api.sales.guard import check_sql
from api.schemas import AskRequest, AskResponse, HistoryTurn, Processing, Ready
from api.store.memory import InMemoryVectorStore
from evals.documents import DOCUMENTS
from evals.scoring import (
    Case,
    declined,
    executed_sql,
    facts_present,
    is_read_only,
    load_cases,
    results_match,
    retrieved_page,
    route_of,
)
from tests.pdf_factory import make_pdf

RESULTS_DIR = Path(__file__).with_name("results")
GROUP_NAMES = {
    "sql": "Text-to-SQL",
    "followup": "Follow-up questions",
    "doc": "Document RAG",
    "decline": "Out-of-scope (should decline)",
    "injection": "Prompt injection",
}
MAX_RATE_LIMIT_RETRIES = 4


# ---------- quota-friendly provider wrappers ----------


class Pacer:
    """Spaces calls at least `60 / rpm` seconds apart and waits out rate limits."""

    def __init__(self, rpm: float, sleep: Callable[[float], None] = time.sleep) -> None:
        self.interval = 60 / rpm if rpm > 0 else 0.0
        self.sleep = sleep
        self._last = 0.0
        self.waited = 0.0  # seconds spent waiting, left out of the measured latency

    def call[T](self, function: Callable[[], T]) -> T:
        for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
            wait = self._last + self.interval - time.monotonic()
            if wait > 0:
                self.sleep(wait)
                self.waited += wait
            self._last = time.monotonic()
            try:
                return function()
            except ProviderRateLimited as error:
                if attempt == MAX_RATE_LIMIT_RETRIES:
                    raise
                delay = (error.retry_after or 30) + 2
                print(f"    rate limited, waiting {delay} s", file=sys.stderr)
                self.sleep(delay)
                self.waited += delay
        raise AssertionError("unreachable")


class CountingChatModel:
    def __init__(self, model: ChatModel, pacer: Pacer) -> None:
        self.model = model
        self.pacer = pacer
        self.calls = 0

    def generate(self, system: str, prompt: str) -> str:
        self.calls += 1
        return self.pacer.call(lambda: self.model.generate(system, prompt))


class PacedEmbedder:
    def __init__(self, embedder: Embedder, pacer: Pacer) -> None:
        self.embedder = embedder
        self.pacer = pacer

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self.pacer.call(lambda: self.embedder.embed_documents(texts))

    def embed_query(self, text: str) -> list[float]:
        return self.pacer.call(lambda: self.embedder.embed_query(text))


# ---------- running ----------


@dataclass
class Outcome:
    id: str
    group: str
    question: str
    passed: bool
    checks: dict[str, bool]
    route: str | None = None
    sql: str | None = None
    answer: str = ""
    model_calls: int = 0
    latency_ms: int = 0
    error: str | None = None


@dataclass
class Report:
    provider: str
    model: str
    started_at: str
    outcomes: list[Outcome] = field(default_factory=list)

    def metrics(self) -> dict[str, tuple[int, int]]:
        """Metric name → (passed, total). Only cases that have the check count towards it."""

        def tally(check: str, groups: Sequence[str] | None = None) -> tuple[int, int]:
            values = [
                o.checks[check]
                for o in self.outcomes
                if check in o.checks and (groups is None or o.group in groups)
            ]
            return sum(values), len(values)

        result = {
            "All cases passed": (sum(o.passed for o in self.outcomes), len(self.outcomes)),
            "Routing accuracy": tally("route"),
            "SQL execution accuracy": tally("sql_result"),
            "Retrieval hit rate (right page in top-k)": tally("retrieved"),
            "Answer contains the expected facts": tally("facts"),
            "Answers with a valid citation": tally("cited"),
            "Out-of-scope questions declined": tally("declined"),
        }
        injection = [o.passed for o in self.outcomes if o.group == "injection"]
        result["Prompt-injection attempts resisted"] = (sum(injection), len(injection))
        return result


def build_agent(
    settings: Settings, rpm: float, sleep: Callable[[float], None] = time.sleep
) -> tuple[ChatAgent, CountingChatModel, SalesDatabase, list[str]]:
    """Builds the production agent with in-memory documents and uploads the evaluation PDFs."""
    raw_embedder, raw_chat = build_providers(settings)
    pacer = Pacer(rpm, sleep)
    embedder, chat = PacedEmbedder(raw_embedder, pacer), CountingChatModel(raw_chat, pacer)

    registry, store = InMemoryDocumentRegistry(), InMemoryVectorStore()
    pipeline = IngestionPipeline(settings, registry, embedder, store)
    file_ids = []
    for name, pages in DOCUMENTS.items():
        record = registry.create(name, Processing(stage="parsing"))
        pipeline.run(record.id, name, make_pdf(pages))
        status = registry.get(record.id).status
        if not isinstance(status, Ready):
            raise RuntimeError(f"Could not ingest {name}: {status}")
        file_ids.append(record.id)

    sales_db = DuckDbSalesDatabase(settings.sql_timeout_s)
    return ChatAgent(settings, embedder, chat, store, sales_db), chat, sales_db, file_ids


def score(
    case: Case, response: AskResponse, sales_db: SalesDatabase, max_rows: int
) -> tuple[dict[str, bool], str]:
    """Returns the checks for one response and the path the agent took."""
    route = route_of(response)
    sql = executed_sql(response)
    checks: dict[str, bool] = {}

    if case.route:
        checks["route"] = route == case.route
    if case.gold_sql:
        predicted = _run(sales_db, sql) if sql else None
        checks["sql_result"] = predicted is not None and any(
            results_match(
                _run(sales_db, check_sql(gold, max_rows)), predicted, case.label_columns, case.compare
            )
            for gold in case.gold_sql
        )
    if case.file and case.page:
        checks["retrieved"] = retrieved_page(response, case.file, case.page)
    if case.facts:
        checks["facts"] = facts_present(response.content, case.facts)
        checks["cited"] = response.grounded
    if case.decline:
        checks["declined"] = declined(response.content)
    if case.read_only:
        checks["read_only"] = is_read_only(sql)
    if case.forbidden:
        answer = response.content.casefold()
        checks["no_forbidden_text"] = not any(text.casefold() in answer for text in case.forbidden)
    return checks, route


def run_cases(
    agent: ChatAgent,
    chat: CountingChatModel,
    sales_db: SalesDatabase,
    file_ids: list[str],
    cases: Sequence[Case],
    report: Report,
    max_rows: int,
    progress: Callable[[Outcome], None] = lambda _: None,
) -> Report:
    for case in cases:
        request = AskRequest(
            question=case.question,
            file_ids=file_ids,
            history=[HistoryTurn(role=role, content=content) for role, content in case.history],
        )
        calls_before, waited_before, started = chat.calls, chat.pacer.waited, time.perf_counter()
        try:
            response = agent.ask(request)
        except ProviderError as error:
            outcome = Outcome(case.id, case.group, case.question, False, {}, error=str(error))
        else:
            checks, route = score(case, response, sales_db, max_rows)
            outcome = Outcome(
                case.id,
                case.group,
                case.question,
                passed=bool(checks) and all(checks.values()),
                checks=checks,
                route=route,
                sql=executed_sql(response),
                answer=response.content,
            )
        outcome.model_calls = chat.calls - calls_before
        waited = chat.pacer.waited - waited_before
        outcome.latency_ms = round((time.perf_counter() - started - waited) * 1000)
        report.outcomes.append(outcome)
        progress(outcome)
    return report


def _run(sales_db: SalesDatabase, sql: str) -> QueryResult | None:
    try:
        return sales_db.run(sql)
    except QueryFailed:
        return None


# ---------- report ----------


def to_markdown(report: Report) -> str:
    calls = [o.model_calls for o in report.outcomes if not o.error]
    latencies = [o.latency_ms for o in report.outcomes if not o.error]
    lines = [
        f"# Evaluation report: {report.provider} ({report.model})",
        "",
        f"Run at {report.started_at} on {len(report.outcomes)} cases from `evals/cases.json`.",
        "",
        "| Metric | Result |",
        "| --- | --- |",
    ]
    for name, (passed, total) in report.metrics().items():
        if total:
            lines.append(f"| {name} | {passed}/{total} ({passed / total:.0%}) |")
    if calls:
        lines.append(f"| Model calls per question (mean) | {statistics.mean(calls):.1f} |")
        lines.append(
            f"| Latency per question (median, excluding quota pacing) | {statistics.median(latencies) / 1000:.1f} s |"
        )

    lines += ["", "## By group", "", "| Group | Passed |", "| --- | --- |"]
    for group, title in GROUP_NAMES.items():
        members = [o for o in report.outcomes if o.group == group]
        if members:
            lines.append(f"| {title} | {sum(o.passed for o in members)}/{len(members)} |")

    failed = [o for o in report.outcomes if not o.passed]
    lines += ["", "## Failed cases", ""]
    if not failed:
        lines.append("None.")
    for outcome in failed:
        failing = [name for name, ok in outcome.checks.items() if not ok]
        lines += [
            f"### {outcome.id}: {outcome.question}",
            "",
            f"- Failed checks: {', '.join(failing) or 'none'}"
            + (f" · error: {outcome.error}" if outcome.error else ""),
            f"- Route taken: {outcome.route}",
        ]
        if outcome.sql:
            lines += ["- SQL that ran:", "", "```sql", outcome.sql, "```"]
        if outcome.answer:
            quoted = outcome.answer.strip().replace("\n", "\n> ")
            lines += ["- Answer:", "", f"> {quoted}"]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--provider", choices=["fake", "gemini"], help="override LLM_PROVIDER")
    parser.add_argument("--only", nargs="+", metavar="ID_OR_GROUP", help="run only these case ids or groups")
    parser.add_argument(
        "--rpm", type=float, default=None, help="max model requests per minute (default 14 for Gemini)"
    )
    parser.add_argument("--out", type=Path, default=RESULTS_DIR, help="where to write the report")
    args = parser.parse_args(argv)

    overrides: dict[str, object] = {"database_url": None}
    if args.provider:
        overrides["llm_provider"] = args.provider
    settings = Settings(**overrides)  # type: ignore[arg-type]
    rpm = args.rpm if args.rpm is not None else (14 if settings.llm_provider == "gemini" else 0)

    cases = load_cases()
    if args.only:
        cases = [c for c in cases if c.id in args.only or c.group in args.only]
    model = settings.gemini_chat_model if settings.llm_provider == "gemini" else "offline stand-in"
    print(f"Evaluating {len(cases)} cases with {settings.llm_provider} ({model}), {rpm or 'unlimited'} rpm")

    agent, chat, sales_db, file_ids = build_agent(settings, rpm)
    report = Report(settings.llm_provider, model, datetime.now().astimezone().isoformat(timespec="seconds"))

    def progress(outcome: Outcome) -> None:
        mark = "PASS" if outcome.passed else "FAIL"
        failing = [name for name, ok in outcome.checks.items() if not ok]
        detail = f"  ({', '.join(failing)})" if failing else (f"  ({outcome.error})" if outcome.error else "")
        print(
            f"  {mark}  {outcome.id:<13} {outcome.model_calls} calls  {outcome.latency_ms / 1000:5.1f} s{detail}"
        )

    run_cases(agent, chat, sales_db, file_ids, cases, report, settings.sql_max_rows, progress)

    markdown = to_markdown(report)
    args.out.mkdir(parents=True, exist_ok=True)
    stem = f"{settings.llm_provider}-{datetime.now():%Y-%m-%d-%H%M}"
    (args.out / f"{stem}.md").write_text(markdown, encoding="utf-8")
    (args.out / f"{stem}.json").write_text(
        json.dumps({**asdict(report), "metrics": report.metrics()}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print()
    print(markdown.split("## By group")[0].strip())
    print(f"\nReport written to {args.out / (stem + '.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
