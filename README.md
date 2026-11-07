# Multisource AI Agent

A RAG and multi-agent assistant: upload documents, ask questions, and get answers where every claim links back to
the passage it came from.

## Repository layout

| Path        | What                                                     | Status      |
| ----------- | -------------------------------------------------------- | ----------- |
| `apps/web`  | Next.js frontend (see [apps/web/README.md](apps/web/README.md)) | Workspace page built |
| `apps/api`  | FastAPI + LangGraph backend                              | Planned     |

## Run the frontend

```bash
cd apps/web
npm install
npm run dev
```

Without a backend it uses built-in sample data, so it works on its own.

## Deploy the frontend to Vercel

1. Import this repository in Vercel.
2. Set **Root Directory** to `apps/web`. The framework is detected as Next.js.
3. Optional: add the `NEXT_PUBLIC_API_URL` environment variable once the backend is deployed.

## CI

`.github/workflows/web-ci.yml` runs lint, type-check, tests, the format check and a production build on every pull
request that touches `apps/web`.
