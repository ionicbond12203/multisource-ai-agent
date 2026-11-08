"""
The graph's nodes. Each one reads the state, does one job, and returns
`(update, summary)` or `(update, summary, status)`: the fields it changes, a
one-line description that the frontend shows in the agent trace, and
optionally "failed" when the step did not succeed.
"""

from typing import Literal

from api.config import Settings
from api.graph.citations import check_citations
from api.graph.prompts import (
    ANSWER_SYSTEM_PROMPT,
    CANNOT_ANSWER,
    DATA_ANSWER_SYSTEM_PROMPT,
    REWRITE_SYSTEM_PROMPT,
    ROUTER_SYSTEM_PROMPT,
    SQL_SYSTEM_PROMPT,
    build_answer_prompt,
    build_rewrite_prompt,
    build_router_prompt,
    build_sql_prompt,
)
from api.graph.state import ChatState
from api.ingestion.extract import extension_of
from api.providers.base import ChatModel, Embedder
from api.sales.database import QueryFailed, QueryResult, SalesDatabase
from api.sales.guard import UnsafeQuery, check_sql
from api.schemas import Source, SourcePassage
from api.store.base import ScoredChunk, VectorStore

NodeResult = tuple[dict[str, object], str] | tuple[dict[str, object], str, Literal["done", "failed"]]

SALES_DB_FILE_ID = "sales-db"
SALES_DB_NAME = "Sales database"
MAX_SQL_ATTEMPTS = 2
MAX_ROWS_SHOWN = 50

CANNOT_ANSWER_MESSAGE = (
    "The sales database doesn't hold the information needed for this question. It covers Sejuk Beverages' "
    "orders, customers, products, warehouses and deliveries from January to September 2026."
)


class ChatNodes:
    def __init__(
        self,
        settings: Settings,
        embedder: Embedder,
        chat_model: ChatModel,
        store: VectorStore,
        sales_db: SalesDatabase,
    ):
        self.settings = settings
        self.embedder = embedder
        self.chat_model = chat_model
        self.store = store
        self.sales_db = sales_db

    # ---------- routing ----------

    def router(self, state: ChatState) -> NodeResult:
        file_count = len(state.get("file_ids", []))
        reply = self.chat_model.generate(
            ROUTER_SYSTEM_PROMPT, build_router_prompt(state["question"], state.get("history", []), file_count)
        )
        if "database" in reply.lower():
            return {"route": "database"}, "Data question → SQL path"
        if not file_count:
            return {"route": "none"}, "Document question, but no files selected"
        return {"route": "documents"}, "Document question → RAG path"

    def rewrite_query(self, state: ChatState) -> NodeResult:
        """
        Turns a follow-up such as "And its temperature?" into a question that
        can be searched on its own. Only runs when there is earlier conversation.
        """
        rewritten = self.chat_model.generate(
            REWRITE_SYSTEM_PROMPT, build_rewrite_prompt(state["question"], state.get("history", []))
        ).strip()
        # Guard against a model that rambles: fall back to the original question.
        query = rewritten.strip('"') if 0 < len(rewritten) <= 500 else state["question"]
        return {"search_query": query}, f'Follow-up rewritten as "{_shorten(query)}"'

    # ---------- documents path ----------

    def retrieve(self, state: ChatState) -> NodeResult:
        query_vector = self.embedder.embed_query(_query(state))
        matches = self.store.search(query_vector, state["file_ids"], self.settings.top_k)
        relevant = [match for match in matches if match.score >= self.settings.effective_min_score]
        if not relevant:
            return {"retrieved": []}, "No chunks above the relevance threshold"
        files = {match.chunk.file_id for match in relevant}
        return (
            {"retrieved": relevant},
            f"Found {len(relevant)} relevant {_plural(len(relevant), 'chunk')} "
            f"in {len(files)} {_plural(len(files), 'file')}",
        )

    def answer(self, state: ChatState) -> NodeResult:
        numbered = [(number, match) for number, match in enumerate(state["retrieved"], start=1)]
        prompt = build_answer_prompt(
            state["question"],
            state.get("history", []),
            [(number, f"{m.chunk.file_name} · {location_of(m)}", m.chunk.text) for number, m in numbered],
        )
        draft = self.chat_model.generate(ANSWER_SYSTEM_PROMPT, prompt)
        sources = [to_source(number, match) for number, match in numbered]
        return (
            {"answer": draft, "sources": sources},
            f"Drafted an answer from {len(sources)} {_plural(len(sources), 'source')}",
        )

    # ---------- database path ----------

    def generate_sql(self, state: ChatState) -> NodeResult:
        retrying = bool(state.get("sql_error"))
        prompt = build_sql_prompt(
            _query(state),
            failed_sql=state.get("draft_sql") if retrying else None,
            error=state.get("sql_error") if retrying else None,
        )
        draft = _strip_code_fence(self.chat_model.generate(SQL_SYSTEM_PROMPT, prompt))
        if draft.upper().startswith(CANNOT_ANSWER):
            return {"failure": CANNOT_ANSWER_MESSAGE}, "The sales data can't answer this question"
        attempt = state.get("sql_attempts", 0) + 1
        summary = (
            "Wrote a SQL query" if attempt == 1 else f"Rewrote the query after the error (attempt {attempt})"
        )
        return {"draft_sql": draft, "sql": "", "sql_error": None, "sql_attempts": attempt}, summary

    def run_sql(self, state: ChatState) -> NodeResult:
        try:
            sql = check_sql(state["draft_sql"], self.settings.sql_max_rows)
        except UnsafeQuery as error:
            return {"sql_error": str(error)}, f"Blocked by the SQL guard: {error}", "failed"
        try:
            result = self.sales_db.run(sql)
        except QueryFailed as error:
            return {"sql": sql, "sql_error": str(error)}, f"Database error: {error}", "failed"
        rows = len(result.rows)
        return (
            {"sql": sql, "sql_error": None, "query_result": result},
            f"Read-only query returned {rows} {_plural(rows, 'row')} in {result.elapsed_ms} ms",
        )

    def answer_from_data(self, state: ChatState) -> NodeResult:
        result = state["query_result"]
        table = format_table(result)
        prompt = build_answer_prompt(
            state["question"],
            state.get("history", []),
            [(1, f"{SALES_DB_NAME} · SQL query and result", f"SQL:\n{state['sql']}\n\n{table}")],
        )
        draft = self.chat_model.generate(DATA_ANSWER_SYSTEM_PROMPT, prompt)
        source = Source(
            kind="sql",
            index=1,
            file_id=SALES_DB_FILE_ID,
            file_name=SALES_DB_NAME,
            location=f"SQL query · {len(result.rows)} {_plural(len(result.rows), 'row')}",
            heading="Query and result",
            score=1.0,
            passages=[SourcePassage(text=state["sql"], cited=False), SourcePassage(text=table, cited=False)],
        )
        return {"answer": draft, "sources": [source]}, "Drafted an answer from the query result"

    # ---------- shared ----------

    def verify_citations(self, state: ChatState) -> NodeResult:
        sources = state["sources"]
        check = check_citations(state["answer"], [source.index for source in sources])
        marked = [_mark_cited(source, source.index in check.cited) for source in sources]

        if check.invalid:
            summary = f"Removed {len(check.invalid)} {_plural(len(check.invalid), 'citation')} with no source"
        elif check.cited:
            count = len(check.cited)
            summary = f"Checked {count} cited {_plural(count, 'source')}: all match"
        else:
            summary = "No citations in the answer → marked not grounded"
        return {"answer": check.text, "sources": marked, "grounded": check.grounded}, summary


def format_table(result: QueryResult, max_rows: int = MAX_ROWS_SHOWN) -> str:
    """Plain-text table for the model and the evidence panel."""
    count = len(result.rows)
    if not count:
        return "Result: no rows"
    shown = result.rows[:max_rows]
    heading = f"Result: {count} {_plural(count, 'row')}" + (
        f" (first {max_rows} shown)" if count > max_rows else ""
    )
    lines = [" | ".join(result.columns)]
    lines += [" | ".join("" if value is None else str(value) for value in row) for row in shown]
    return heading + "\n" + "\n".join(lines)


def location_of(match: ScoredChunk) -> str:
    chunk = match.chunk
    if extension_of(chunk.file_name) == ".pdf":
        return f"Page {chunk.page} of {chunk.page_count}"
    return "Text file"


def to_source(number: int, match: ScoredChunk) -> Source:
    return Source(
        index=number,
        file_id=match.chunk.file_id,
        file_name=match.chunk.file_name,
        location=location_of(match),
        score=round(match.score, 3),
        passages=[SourcePassage(text=match.chunk.text, cited=False)],
    )


def _query(state: ChatState) -> str:
    return state.get("search_query") or state["question"]


def _strip_code_fence(text: str) -> str:
    """Models sometimes wrap SQL in ```sql … ``` despite being told not to."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    return text.strip()


def _mark_cited(source: Source, cited: bool) -> Source:
    passages = [passage.model_copy(update={"cited": cited}) for passage in source.passages]
    return source.model_copy(update={"passages": passages})


def _shorten(text: str, limit: int = 80) -> str:
    return text if len(text) <= limit else f"{text[: limit - 1]}…"


def _plural(count: int, word: str) -> str:
    return word if count == 1 else f"{word}s"
