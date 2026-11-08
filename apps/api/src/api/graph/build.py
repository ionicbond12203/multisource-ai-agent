"""
Wires the nodes into a LangGraph graph and runs it for one question.

    START → router ─┬─ first question ──────────────→ retrieve ─┬─ found ───→ answer → verify_citations → END
                    ├─ follow-up ─→ rewrite_query ──↗           └─ nothing ─→ END
                    └─ no files ──→ END
"""

import time
import uuid
from collections.abc import Callable

from langgraph.graph import END, START, StateGraph

from api.config import Settings
from api.graph.nodes import ChatNodes, NodeResult
from api.graph.state import ChatState
from api.providers.base import ChatModel, Embedder
from api.schemas import AgentRun, AgentStep, AskRequest, AskResponse
from api.store.base import VectorStore

NO_FILES_ANSWER = (
    "No files are selected. Switch on at least one file in the knowledge base, or upload a document first."
)
NOT_FOUND_ANSWER = (
    "I couldn't find this in the files you selected. Try switching on more files in the knowledge base, "
    "or upload a document that covers it."
)


class ChatAgent:
    def __init__(self, settings: Settings, embedder: Embedder, chat_model: ChatModel, store: VectorStore):
        nodes = ChatNodes(settings, embedder, chat_model, store)

        graph = StateGraph(ChatState)
        graph.add_node("router", _traced("router", nodes.router))
        graph.add_node("rewrite_query", _traced("rewrite_query", nodes.rewrite_query))
        graph.add_node("retrieve", _traced("retrieve", nodes.retrieve))
        graph.add_node("answer", _traced("answer", nodes.answer))
        graph.add_node("verify_citations", _traced("verify_citations", nodes.verify_citations))

        graph.add_edge(START, "router")
        graph.add_conditional_edges(
            "router",
            _after_router,
            {"rewrite": "rewrite_query", "retrieve": "retrieve", "none": END},
        )
        graph.add_edge("rewrite_query", "retrieve")
        graph.add_conditional_edges(
            "retrieve",
            lambda s: "found" if s["retrieved"] else "nothing",
            {"found": "answer", "nothing": END},
        )
        graph.add_edge("answer", "verify_citations")
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

        if "answer" not in result:
            content = NO_FILES_ANSWER if result.get("route") == "none" else NOT_FOUND_ANSWER
        else:
            content = result["answer"]

        return AskResponse(
            content=content,
            sources=result.get("sources", []),
            grounded=result.get("grounded", False),
            follow_ups=[],
            run=AgentRun(steps=result["steps"], total_ms=total_ms),
        )


def _after_router(state: ChatState) -> str:
    if state["route"] == "none":
        return "none"
    return "rewrite" if state.get("history") else "retrieve"


def _traced(name: str, node: Callable[[ChatState], NodeResult]) -> Callable[[ChatState], dict[str, object]]:
    """Wraps a node so it records how long it took and what it did."""

    def run(state: ChatState) -> dict[str, object]:
        started = time.perf_counter()
        update, summary = node(state)
        step = AgentStep(
            id=f"{name}-{uuid.uuid4().hex[:6]}",
            node=name,
            summary=summary,
            duration_ms=_elapsed_ms(started),
            status="done",
        )
        return {**update, "steps": [step]}

    return run


def _elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)
