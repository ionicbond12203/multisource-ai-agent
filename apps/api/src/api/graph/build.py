"""
Wires the nodes into a LangGraph graph and runs it for one question.

    START → router ─┬─ documents ─→ retrieve ─┬─ found ───→ answer ───────────┐
                    │                         └─ nothing ─→ END               ├─→ verify_citations → END
                    ├─ database ──→ generate_sql → run_sql ─┬─ ok ─→ answer_from_data ┘
                    │                     ↑                 ├─ error, retry left ─┐
                    │                     └─────────────────┼─────────────────────┘
                    │                                       └─ error, no retries ─→ END
                    └─ none ─→ END

The router makes one model call that both picks the source (uploaded documents
or the sales database) and rewrites a follow-up into a standalone question.
"""

import time
import uuid
from collections.abc import Callable

from langgraph.graph import END, START, StateGraph

from api.config import Settings
from api.graph.nodes import MAX_SQL_ATTEMPTS, ChatNodes, NodeResult
from api.graph.state import ChatState
from api.providers.base import ChatModel, Embedder
from api.sales.database import SalesDatabase
from api.schemas import AgentRun, AgentStep, AskRequest, AskResponse
from api.store.base import VectorStore

NO_FILES_ANSWER = (
    "No files are selected. Switch on or upload a document, or ask about Sejuk Beverages' sales, orders "
    "and deliveries, which I can look up in the sales database."
)
NOT_FOUND_ANSWER = (
    "I couldn't find this in the files you selected. Try switching on more files in the knowledge base, "
    "or upload a document that covers it."
)


class ChatAgent:
    def __init__(
        self,
        settings: Settings,
        embedder: Embedder,
        chat_model: ChatModel,
        store: VectorStore,
        sales_db: SalesDatabase,
    ):
        nodes = ChatNodes(settings, embedder, chat_model, store, sales_db)

        graph = StateGraph(ChatState)
        for name in (
            "router",
            "retrieve",
            "answer",
            "generate_sql",
            "run_sql",
            "answer_from_data",
            "verify_citations",
        ):
            graph.add_node(name, _traced(name, getattr(nodes, name)))

        graph.add_edge(START, "router")
        graph.add_conditional_edges(
            "router",
            lambda s: s["route"],
            {"documents": "retrieve", "database": "generate_sql", "none": END},
        )

        graph.add_conditional_edges(
            "retrieve",
            lambda s: "found" if s["retrieved"] else "nothing",
            {"found": "answer", "nothing": END},
        )
        graph.add_edge("answer", "verify_citations")

        graph.add_conditional_edges(
            "generate_sql", lambda s: "stop" if s.get("failure") else "run", {"run": "run_sql", "stop": END}
        )
        graph.add_conditional_edges(
            "run_sql",
            _after_run_sql,
            {"ok": "answer_from_data", "retry": "generate_sql", "give_up": END},
        )
        graph.add_edge("answer_from_data", "verify_citations")

        graph.add_edge("verify_citations", END)
        self._graph = graph.compile()

    def ask(self, request: AskRequest) -> AskResponse:
        started = time.perf_counter()
        result: ChatState = self._graph.invoke(
            {
                "question": request.question,
                "history": [(turn.role, turn.content) for turn in request.history],
                "file_ids": request.file_ids,
                "steps": [],
            }
        )
        total_ms = _elapsed_ms(started)

        return AskResponse(
            content=result["answer"] if "answer" in result else _no_answer_message(result),
            sources=result.get("sources", []),
            grounded=result.get("grounded", False),
            follow_ups=[],
            run=AgentRun(steps=result["steps"], total_ms=total_ms),
        )


def _after_run_sql(state: ChatState) -> str:
    if not state.get("sql_error"):
        return "ok"
    return "retry" if state.get("sql_attempts", 0) < MAX_SQL_ATTEMPTS else "give_up"


def _no_answer_message(state: ChatState) -> str:
    if state.get("failure"):
        return state["failure"]
    if state.get("sql_error"):
        return (
            f"I couldn't get an answer from the sales database. The last attempt failed: {state['sql_error']}"
        )
    if state.get("route") == "none":
        return NO_FILES_ANSWER
    return NOT_FOUND_ANSWER


def _traced(name: str, node: Callable[[ChatState], NodeResult]) -> Callable[[ChatState], dict[str, object]]:
    """Wraps a node so it records how long it took, what it did and whether it worked."""

    def run(state: ChatState) -> dict[str, object]:
        started = time.perf_counter()
        update, summary, *rest = node(state)
        step = AgentStep(
            id=f"{name}-{uuid.uuid4().hex[:6]}",
            node=name,
            summary=summary,
            duration_ms=_elapsed_ms(started),
            status=rest[0] if rest else "done",
        )
        return {**update, "steps": [step]}

    return run


def _elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)
