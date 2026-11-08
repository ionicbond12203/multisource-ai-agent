"""
The graph's nodes. Each one reads the state, does one job, and returns
`(update, summary)`: the fields it changes and a one-line description that the
frontend shows in the agent trace.
"""

from api.config import Settings
from api.graph.citations import check_citations
from api.graph.prompts import (
    ANSWER_SYSTEM_PROMPT,
    REWRITE_SYSTEM_PROMPT,
    build_answer_prompt,
    build_rewrite_prompt,
)
from api.graph.state import ChatState
from api.ingestion.extract import extension_of
from api.providers.base import ChatModel, Embedder
from api.schemas import Source, SourcePassage
from api.store.base import ScoredChunk, VectorStore

NodeResult = tuple[dict[str, object], str]


class ChatNodes:
    def __init__(self, settings: Settings, embedder: Embedder, chat_model: ChatModel, store: VectorStore):
        self.settings = settings
        self.embedder = embedder
        self.chat_model = chat_model
        self.store = store

    def router(self, state: ChatState) -> NodeResult:
        # Step 3 makes this an LLM decision between documents and the SQL database.
        if not state.get("file_ids"):
            return {"route": "none"}, "No files selected → nothing to search"
        return {"route": "rag"}, "Document question → RAG path"

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

    def retrieve(self, state: ChatState) -> NodeResult:
        query_vector = self.embedder.embed_query(state.get("search_query") or state["question"])
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
        retrieved = state["retrieved"]
        numbered = [(number, location_of(match), match) for number, match in enumerate(retrieved, start=1)]
        prompt = build_answer_prompt(state["question"], state.get("history", []), numbered)
        draft = self.chat_model.generate(ANSWER_SYSTEM_PROMPT, prompt)
        sources = [to_source(number, location, match) for number, location, match in numbered]
        return (
            {"answer": draft, "sources": sources},
            f"Drafted an answer from {len(sources)} {_plural(len(sources), 'source')}",
        )

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


def location_of(match: ScoredChunk) -> str:
    chunk = match.chunk
    if extension_of(chunk.file_name) == ".pdf":
        return f"Page {chunk.page} of {chunk.page_count}"
    return "Text file"


def to_source(number: int, location: str, match: ScoredChunk) -> Source:
    return Source(
        index=number,
        file_id=match.chunk.file_id,
        file_name=match.chunk.file_name,
        location=location,
        score=round(match.score, 3),
        passages=[SourcePassage(text=match.chunk.text, cited=False)],
    )


def _mark_cited(source: Source, cited: bool) -> Source:
    passages = [passage.model_copy(update={"cited": cited}) for passage in source.passages]
    return source.model_copy(update={"passages": passages})


def _shorten(text: str, limit: int = 80) -> str:
    return text if len(text) <= limit else f"{text[: limit - 1]}…"


def _plural(count: int, word: str) -> str:
    return word if count == 1 else f"{word}s"
