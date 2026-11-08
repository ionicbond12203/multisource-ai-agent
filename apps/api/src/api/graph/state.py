"""The state that flows through the chat graph."""

import operator
from typing import Annotated, Literal, TypedDict

from api.schemas import AgentStep, Source
from api.store.base import ScoredChunk

Route = Literal["rag", "none"]


class ChatState(TypedDict, total=False):
    # Input
    question: str
    history: list[tuple[str, str]]  # (role, content), oldest first
    file_ids: list[str]

    # Filled in by the nodes
    route: Route
    search_query: str  # standalone version of a follow-up question
    retrieved: list[ScoredChunk]
    answer: str
    sources: list[Source]
    grounded: bool

    # Every node appends one step. `operator.add` tells LangGraph to concatenate
    # the lists instead of replacing them.
    steps: Annotated[list[AgentStep], operator.add]
