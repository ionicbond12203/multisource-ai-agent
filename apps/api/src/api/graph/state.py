"""The state that flows through the chat graph."""

import operator
from typing import Annotated, Literal, TypedDict

from api.sales.database import QueryResult
from api.schemas import AgentStep, Source
from api.store.base import ScoredChunk

# documents: search the uploaded files. database: query the sales database. none: nothing to do.
Route = Literal["documents", "database", "none"]


class ChatState(TypedDict, total=False):
    # Input
    question: str
    history: list[tuple[str, str]]  # (role, content), oldest first
    file_ids: list[str]

    # Filled in by the nodes
    route: Route
    search_query: str  # standalone version of a follow-up question

    # Documents path
    retrieved: list[ScoredChunk]

    # Database path
    draft_sql: str  # SQL as the model wrote it
    sql: str  # the checked, row-limited SQL that ran (or was about to)
    sql_error: str | None  # why the last attempt failed; sent back to the model
    sql_attempts: int
    query_result: QueryResult

    # Output
    answer: str
    sources: list[Source]
    grounded: bool
    failure: str  # message for the user when the graph stops without an answer

    # Every node appends one step. `operator.add` tells LangGraph to concatenate
    # the lists instead of replacing them.
    steps: Annotated[list[AgentStep], operator.add]
