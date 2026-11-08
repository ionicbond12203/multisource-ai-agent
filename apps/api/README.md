# Multisource API

FastAPI + LangGraph backend for the Multisource AI Agent. Upload documents, ask questions, get answers
where every claim cites the passage it came from.

It implements the contract in [`apps/web/README.md`](../web/README.md#backend-contract), so the frontend
works with it unchanged.

## Run it

Requires [uv](https://docs.astral.sh/uv/). It installs the right Python (3.13) for you.

```bash
cd apps/api
uv sync
uv run uvicorn api.main:app --reload
```

- API: http://localhost:8000
- Interactive docs (try every endpoint in the browser): http://localhost:8000/docs

Connect the frontend: in `apps/web/.env.local` set `NEXT_PUBLIC_API_URL=http://localhost:8000`, then restart
`npm run dev`.

No API key is needed. By default the API uses offline stand-in models (see [Providers](#providers)).

## Commands

| Command                                   | What it does               |
| ----------------------------------------- | -------------------------- |
| `uv run pytest`                           | Run the tests              |
| `uv run ruff check .`                     | Lint                       |
| `uv run ruff format .`                    | Format the code            |
| `docker build -t multisource-api .`       | Build the production image |
| `docker run -p 8000:8000 multisource-api` | Run the image              |

CI (`.github/workflows/api-ci.yml`) runs lint, the format check, the tests and the Docker build on every pull
request that touches `apps/api`.

## How a question is answered

`POST /chat` runs a LangGraph graph (`src/api/graph/build.py`):

```
START → router ─┬─ rag ──→ retrieve ─┬─ found ───→ answer → verify_citations → END
                │                    └─ nothing ─→ END   ("not found in your files")
                └─ none ─→ END                         ("no files selected")
```

| Node               | Job                                                                                        |
| ------------------ | ------------------------------------------------------------------------------------------ |
| `router`           | Decides which path to take. Today: documents or nothing. Later: documents or SQL.          |
| `retrieve`         | Embeds the question, searches only the selected files, drops low-scoring chunks.           |
| `answer`           | Numbers the chunks as sources [1], [2] … and asks the chat model to answer with citations. |
| `verify_citations` | Removes citations that match no source and sets `grounded`.                                |

Every node records a step (name, summary, duration). They are returned in `run.steps`, and the frontend
shows them as the agent trace.

## How a file is processed

`POST /documents` stores the upload and returns at once with `processing`. A background task then runs
`src/api/ingestion/pipeline.py`:

```
parsing → chunking → embedding → indexing → ready
```

Each stage updates the status that `GET /documents/{id}` returns, which the frontend polls. Failures end in a
`failed` status with a reason the user can act on, for example a scanned PDF with no text gets
`recovery: "ocr"`.

Supported now: `.pdf`, `.txt`, `.md`. Other types fail with a clear message.

## Layout

```
src/api/
├── main.py            App factory: CORS, routes, /health
├── config.py          Settings from environment variables (see .env.example)
├── schemas.py         JSON models, mirror the frontend's TypeScript types
├── services.py        Builds and wires every component; the one place to swap implementations
├── routes/
│   ├── chat.py        POST /chat
│   └── documents.py   POST /documents, GET /documents/{id}, POST /documents/{id}/ocr
├── ingestion/
│   ├── extract.py     File → text per page
│   ├── chunking.py    Text → overlapping chunks, each within one page
│   ├── registry.py    Document status store
│   └── pipeline.py    Runs the stages and updates the status
├── graph/
│   ├── build.py       Graph wiring and the ChatAgent entry point
│   ├── nodes.py       The four nodes
│   ├── state.py       State passed between nodes
│   ├── prompts.py     Prompt text
│   └── citations.py   Citation checking
├── providers/
│   ├── base.py        Embedder and ChatModel interfaces
│   └── fake.py        Offline implementations
└── store/
    ├── base.py        VectorStore interface
    └── memory.py      In-memory implementation
tests/                 pytest; builds its own PDFs, needs no network or keys
```

## Providers

Code depends only on the interfaces in `providers/base.py` and `store/base.py`. `services.py` picks the
implementations.

| Part         | Now                                                      | Planned                      |
| ------------ | -------------------------------------------------------- | ---------------------------- |
| Chat model   | `ExtractiveChatModel`: quotes the best-matching sentence | Gemini (free tier)           |
| Embeddings   | `HashingEmbedder`: matches shared words, not meaning     | Gemini embeddings            |
| Vector store | In memory, lost on restart                               | Supabase Postgres + pgvector |
| File status  | In memory, lost on restart                               | Supabase Postgres            |

To add a provider: implement `Embedder` and `ChatModel`, add a case to `build_providers` in
`providers/__init__.py`, and allow the new value in `Settings.llm_provider`.

## Common changes

| I want to…                               | Change                                                         |
| ---------------------------------------- | -------------------------------------------------------------- |
| Change a JSON field                      | `schemas.py` and the frontend's `types.ts` together            |
| Tune chunk size or the relevance cut-off | Environment variables, see `.env.example`                      |
| Change how the model is instructed       | `graph/prompts.py`                                             |
| Add a node to the graph                  | A method in `graph/nodes.py`, then wire it in `graph/build.py` |
| Support another file type                | `ingestion/extract.py` (`SUPPORTED_EXTENSIONS` and a reader)   |

## Not built yet

- Real models and a persistent database (step 2)
- SQL agent over the sample distributor database (step 3)
- Guardrails: PII masking and prompt-injection checks (step 4)
- OCR for scanned PDFs, follow-up question rewriting, rate limiting
