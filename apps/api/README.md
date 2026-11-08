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

No API key is needed. By default the API uses offline stand-in models and keeps everything in memory (see
[Providers](#providers)). For real answers, set up [Gemini and Supabase](#use-real-models-and-a-database).

## Use real models and a database

Both are free and need no credit card.

1. **Gemini key.** Sign in at https://aistudio.google.com/apikey and create an API key.
2. **Supabase project.** Create a project at https://supabase.com (free plan). Open **Connect**, choose
   **Session pooler**, and copy the connection string. Replace `[YOUR-PASSWORD]` with the database password you
   set when creating the project.
3. **`.env`.** Copy `.env.example` to `.env` and set:

   ```bash
   LLM_PROVIDER=gemini
   GEMINI_API_KEY=your-key
   DATABASE_URL=postgresql://postgres.xxxx:password@aws-0-xx.pooler.supabase.com:5432/postgres
   ```

4. Restart the API. It creates its tables on startup (`src/api/postgres/schema.sql`).

`.env` is git-ignored. Never commit keys. On a free Supabase project, 7 days without requests pauses it;
unpause it from the Supabase dashboard.

## Commands

| Command                                   | What it does                                                                 |
| ----------------------------------------- | ---------------------------------------------------------------------------- |
| `uv run pytest`                           | Run the tests                                                                |
| `docker compose up -d db`                 | Start a local Postgres for the Postgres tests (see `tests/test_postgres.py`) |
| `uv run ruff check .`                     | Lint                                                                         |
| `uv run ruff format .`                    | Format the code                                                              |
| `docker build -t multisource-api .`       | Build the production image                                                   |
| `docker run -p 8000:8000 multisource-api` | Run the image                                                                |

CI (`.github/workflows/api-ci.yml`) runs lint, the format check, the tests (including the Postgres tests,
against a throwaway database) and the Docker build on every pull request that touches `apps/api`.

Two test files skip themselves unless configured: `test_postgres.py` needs `TEST_DATABASE_URL`, and
`test_gemini_live.py` needs `GEMINI_API_KEY` plus `RUN_LIVE_TESTS=1` (it uses real quota, so CI never runs it).

## How a question is answered

`POST /chat` runs a LangGraph graph (`src/api/graph/build.py`):

```
START → router
          ├─ documents ─→ retrieve ─┬─ found ───→ answer ─────────────────────┐
          │                         └─ nothing ─→ END  ("not found")          ├─→ verify_citations → END
          ├─ database ──→ generate_sql → run_sql ─┬─ ok ──→ answer_from_data ─┘
          │                    ↑                  ├─ error, 1 retry left ─┐
          │                    └──────────────────┼───────────────────────┘
          │                                       └─ error again ─→ END  ("couldn't get an answer")
          └─ none ─→ END  ("no files selected")
```

| Node               | Job                                                                                                                                       |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `router`           | One model call: documents or sales database? For a follow-up, also restates it on its own ("And in July?" → "…excursions in July 2026?"). |
| `retrieve`         | Embeds the question, searches only the selected files, drops low-scoring chunks.                                                          |
| `answer`           | Numbers the chunks as sources [1], [2] … and asks the chat model to answer with citations.                                                |
| `generate_sql`     | Writes one PostgreSQL query from the schema description. On a retry it sees its last error.                                               |
| `run_sql`          | Checks the SQL with the guard, then runs it read-only. A rejection or error is a failed step.                                             |
| `answer_from_data` | Answers from the query result, which becomes source [1] (`kind: "sql"`).                                                                  |
| `verify_citations` | Removes citations that match no source and sets `grounded`.                                                                               |

## The sales database (SQL agent)

A fictional Malaysian drinks distributor, Sejuk Beverages Sdn Bhd, with orders from January to September
2026: `warehouses`, `customers`, `products`, `orders`, `order_items`, `deliveries`. `src/api/sales/data.py`
generates it deterministically and builds in a few patterns worth finding (a Ramadan sales peak, monsoon
delays in Kuantan in Q1, a faulty reefer in Penang in August). It is loaded on startup into Postgres (schema
`distribution`) when `DATABASE_URL` is set, or into an embedded read-only DuckDB file when it isn't.

The model's SQL is untrusted, since a user can try to talk it into anything. Layers of protection:

| Layer                 | Where                        | Stops                                                         |
| --------------------- | ---------------------------- | ------------------------------------------------------------- |
| SQL guard             | `sales/guard.py`             | Anything but one SELECT; other tables; `pg_sleep`, file reads |
| Row limit             | `sales/guard.py`             | Huge results (`LIMIT 200` added or lowered)                   |
| Read-only transaction | `postgres/sales_database.py` | Writes, even if the guard missed one                          |
| `sales_reader` role   | `postgres/sales_database.py` | Reading anything outside the `distribution` schema            |
| Statement timeout     | both database classes        | Queries that run for more than 5 seconds                      |
| Prompt rules          | `graph/prompts.py`           | The model following instructions hidden in the question       |

`tests/test_sales_guard.py` lists the attacks that are blocked.

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
│   ├── registry.py    Document status store (interface + in-memory)
│   └── pipeline.py    Runs the stages and updates the status
├── graph/
│   ├── build.py       Graph wiring and the ChatAgent entry point
│   ├── nodes.py       The nodes
│   ├── state.py       State passed between nodes
│   ├── prompts.py     Prompt text
│   └── citations.py   Citation checking
├── providers/
│   ├── base.py        Embedder and ChatModel interfaces
│   ├── fake.py        Offline implementations
│   └── gemini.py      Google Gemini (chat + embeddings)
├── sales/
│   ├── schema.py      Tables, whitelist and the description the model sees
│   ├── data.py        Deterministic sample data
│   ├── guard.py       SQL checks (the security boundary)
│   └── database.py    SalesDatabase interface + offline DuckDB version
├── store/
│   ├── base.py        VectorStore interface
│   └── memory.py      In-memory implementation
└── postgres/
    ├── schema.sql     Tables, applied at startup
    ├── vector_store.py       pgvector VectorStore
    ├── document_registry.py  Document status in Postgres
    └── sales_database.py     Sales data in Postgres, read-only role
tests/                 pytest; builds its own PDFs, needs no network or keys by default
```

## Providers

Code depends only on the interfaces in `providers/base.py` and `store/base.py`. `services.py` picks the
implementations.

| Part         | Default (offline)                                        | With `.env` set up                                             |
| ------------ | -------------------------------------------------------- | -------------------------------------------------------------- |
| Chat model   | `ExtractiveChatModel`: quotes the best-matching sentence | Gemini `gemini-3.5-flash-lite`                                 |
| Embeddings   | `HashingEmbedder`: matches shared words, not meaning     | Gemini `gemini-embedding-001`, 768 dimensions                  |
| Vector store | In memory, lost on restart                               | Postgres + pgvector (`DATABASE_URL`)                           |
| File status  | In memory, lost on restart                               | Postgres; unfinished uploads are marked failed after a restart |

Gemini errors become `ProviderError` (shown to the user, HTTP 502) or `ProviderRateLimited` when the free
quota runs out (HTTP 429). The SDK retries 429 and 5xx responses a few times before that.

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

## Running as a free public demo

Gemini's free tier allows 15 model calls a minute for the whole app. A document question takes 2 calls
(router, answer) and a data question 3 (router, SQL, answer), so the API protects that budget:

| Protection              | Where                 | Default                                                      |
| ----------------------- | --------------------- | ------------------------------------------------------------ |
| Per-visitor limits      | `rate_limit.py`       | 4 questions a minute, 50 a day; 10 uploads an hour           |
| App-wide question limit | `rate_limit.py`       | 5 questions a minute (5 × 3 calls = 15)                      |
| No retries on quota 429 | `providers/gemini.py` | Only 5xx and timeouts are retried; a 429 is reported at once |

Limited requests get HTTP 429 with a `Retry-After` header and a message saying how long to wait, which the
frontend shows. Counters are in memory, which suits the single free Render instance; several instances would
need a shared store such as Redis. Change the limits with the variables in `.env.example`.

The free Render instance sleeps after about 15 idle minutes, and the first request then takes up to a minute.
The frontend polls `GET /health` on load and shows a "waking up" notice meanwhile.

## Not built yet

- Guardrails: PII masking and prompt-injection checks (step 4)
- OCR for scanned PDFs, deleting old uploads
