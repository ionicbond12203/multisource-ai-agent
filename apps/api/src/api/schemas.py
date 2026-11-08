"""
JSON shapes shared with the frontend.

These mirror `apps/web/src/features/workspace/types.ts` and `api/types.ts`.
Python code uses snake_case; the JSON uses camelCase. `CamelModel` converts
between the two, so `follow_ups` in Python is `followUps` on the wire.

If you change a model here, change the TypeScript type too (and vice versa).
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base model: camelCase JSON, snake_case Python, accepts either on input."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, serialize_by_alias=True)


# ---------- Document status (FileStatus in TypeScript) ----------

IngestionStage = Literal["parsing", "chunking", "embedding", "indexing"]


class Uploading(CamelModel):
    kind: Literal["uploading"] = "uploading"
    progress: float = Field(ge=0, le=1)


class Processing(CamelModel):
    kind: Literal["processing"] = "processing"
    stage: IngestionStage
    progress: float | None = Field(default=None, ge=0, le=1)


class Ready(CamelModel):
    kind: Literal["ready"] = "ready"
    pages: int
    chunks: int


class Failed(CamelModel):
    kind: Literal["failed"] = "failed"
    reason: str
    recovery: Literal["ocr", "retry"] | None = None


FileStatus = Annotated[Uploading | Processing | Ready | Failed, Field(discriminator="kind")]


class DocumentResponse(CamelModel):
    """Body of POST /documents, GET /documents/{id} and POST /documents/{id}/ocr."""

    id: str
    status: FileStatus


# ---------- Chat ----------


class HistoryTurn(CamelModel):
    role: Literal["user", "assistant"]
    content: str


class AskRequest(CamelModel):
    """Body of POST /chat."""

    question: str = Field(min_length=1, max_length=2000)
    file_ids: list[str] = Field(default_factory=list)
    history: list[HistoryTurn] = Field(default_factory=list)


class SourcePassage(CamelModel):
    text: str
    cited: bool


class Source(CamelModel):
    # "document": passages from an uploaded file. "sql": the query and its result table.
    kind: Literal["document", "sql"] = "document"
    index: int
    file_id: str
    file_name: str
    location: str
    heading: str | None = None
    score: float = Field(ge=0, le=1)
    passages: list[SourcePassage]


AgentStepStatus = Literal["running", "done", "failed"]


class AgentStep(CamelModel):
    id: str
    node: str
    summary: str
    duration_ms: int
    status: AgentStepStatus


class AgentRun(CamelModel):
    steps: list[AgentStep]
    total_ms: int


class AskResponse(CamelModel):
    """Body returned by POST /chat."""

    content: str
    sources: list[Source]
    run: AgentRun
    grounded: bool
    follow_ups: list[str]


# ---------- Sales database (GET /sales/tables, GET /sales/tables/{name}/rows) ----------

CellValue = str | int | float | bool | None


class SalesColumn(CamelModel):
    name: str
    type: str
    description: str


class SalesTable(CamelModel):
    name: str
    description: str
    row_count: int
    primary_key: list[str]
    columns: list[SalesColumn]


class SalesDatabaseInfo(CamelModel):
    company: str
    period: str
    tables: list[SalesTable]


class TableRows(CamelModel):
    """One page of a table's rows."""

    table: str
    columns: list[str]
    # Values in column order. Dates and times are ISO strings.
    rows: list[list[CellValue]]
    total: int
    offset: int
    limit: int
    sort: str | None
    order: Literal["asc", "desc"]
