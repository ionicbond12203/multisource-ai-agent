# Multisource AI Agent

A RAG and multi-agent assistant: upload documents, ask questions, and get answers where every claim links back to
the passage it came from.

## Repository layout

| Path       | What                                                                       | Status                           |
| ---------- | -------------------------------------------------------------------------- | -------------------------------- |
| `apps/web` | Next.js frontend (see [apps/web/README.md](apps/web/README.md))            | Workspace page built             |
| `apps/api` | FastAPI + LangGraph backend (see [apps/api/README.md](apps/api/README.md)) | Document Q&A with offline models |

## Run the frontend

```bash
cd apps/web
npm install
npm run dev
```

Without a backend it uses built-in sample data, so it works on its own.

## Run the backend

```bash
cd apps/api
uv sync
uv run uvicorn api.main:app --reload
```

Then set `NEXT_PUBLIC_API_URL=http://localhost:8000` in `apps/web/.env.local` and restart the frontend.

## Deploy the frontend to Vercel

1. Import this repository in Vercel.
2. Set **Root Directory** to `apps/web`. The framework is detected as Next.js.
3. Optional: add the `NEXT_PUBLIC_API_URL` environment variable once the backend is deployed.

## CI

`.github/workflows/web-ci.yml` runs lint, type-check, tests, the format check and a production build on every pull
request that touches `apps/web`. `.github/workflows/api-ci.yml` runs lint, the format check, tests and a Docker
build on every pull request that touches `apps/api`.
