# Multisource web app

Next.js frontend for the Multisource RAG agent: upload documents, ask questions, and check every answer against
the cited passages.

It runs on built-in sample data until a backend URL is set, so it can be developed and demoed on its own.

## Quick start

```bash
cd apps/web
npm install
npm run dev          # http://localhost:3000
```

To use the real backend, copy `.env.example` to `.env.local` and set `NEXT_PUBLIC_API_URL`.

| Script               | What it does                                                  |
| -------------------- | ------------------------------------------------------------- |
| `npm run dev`        | Development server with hot reload                            |
| `npm run build`      | Production build                                              |
| `npm run test`       | Unit and component tests (Vitest + Testing Library)           |
| `npm run test:watch` | Tests in watch mode                                           |
| `npm run lint`       | ESLint                                                        |
| `npm run typecheck`  | Generates Next.js route types, then runs TypeScript           |
| `npm run format`     | Format every file with Prettier (also sorts Tailwind classes) |
| `npm run check`      | Lint + typecheck + tests + format check, as run in CI         |

Requires Node.js 20.9 or newer (CI uses the version in `/.nvmrc`).

## Stack

- **Next.js 16** (App Router, Cache Components) and **React 19**
- **Tailwind CSS 4**, with design tokens in `src/app/globals.css`
- **react-markdown** for answers, **lucide-react** for icons
- Fonts self-hosted from npm via `@fontsource-variable/*`, so builds never call Google Fonts

> Next.js 16 changed several APIs. Before relying on older tutorials, check the docs bundled at
> `node_modules/next/dist/docs/` (see `AGENTS.md`).

## Folder structure

```
src/
├── app/                         Routes only: layout, page, global CSS
│   ├── globals.css              Design tokens (colours, fonts). Rebrand here.
│   ├── layout.tsx
│   └── page.tsx                 Workspace page: header + <WorkspaceShell>
├── components/                  Shared across features
│   ├── app-header.tsx
│   └── ui/                      Small primitives: Button, Badge, LogoMark
├── config/site.ts               Product name, nav items, upload limits
├── lib/utils.ts                 cn(), formatBytes(), createId() …
├── test/setup.ts                Vitest setup
└── features/workspace/          Everything specific to the Workspace page
    ├── index.ts                 Public exports; import the feature from here
    ├── types.ts                 Domain types (files, messages, sources, agent runs)
    ├── api/
    │   ├── types.ts             Frontend ↔ backend contract
    │   ├── http-clients.ts      Real FastAPI clients
    │   ├── mock-clients.ts      Sample-data clients used without a backend
    │   └── index.ts             Picks real or mock from NEXT_PUBLIC_API_URL
    ├── hooks/use-workspace.ts   Wires the reducer to the API; exposes actions
    ├── lib/
    │   ├── workspace-reducer.ts All page state + selectors (pure, unit-tested)
    │   ├── citations.ts         "[1]" markers → clickable citation chips
    │   ├── upload-rules.ts      File type and size validation
    │   ├── initial-state.ts     Empty and demo starting states
    │   └── mock-data.ts         Sample content (fictional company)
    └── components/              UI, one component per file
        ├── workspace-shell.tsx  3-column layout, owns the useWorkspace() hook
        ├── knowledge-sidebar.tsx, knowledge-file-row.tsx, upload-dropzone.tsx
        ├── chat-panel.tsx, assistant-message.tsx, agent-run-card.tsx,
        │   agent-steps.tsx, citation-chip.tsx, composer.tsx
        └── evidence-panel.tsx, source-card.tsx, document-preview.tsx
```

### How data flows

```
User action ─▶ component ─▶ actions.* (use-workspace.ts) ─▶ API client ─▶ backend
                                     │
                                     ▼
                         dispatch(action) ─▶ workspaceReducer ─▶ new state ─▶ components re-render
```

- **Components** receive data and callbacks through props and never call the API.
- **`use-workspace.ts`** is the only place with side effects (requests, cancellation, error handling).
- **`workspace-reducer.ts`** holds every state change, so behaviour can be tested without a browser.

## Common changes

| I want to…                                | Change                                                                                           |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Rename the product or edit the nav        | `src/config/site.ts`                                                                             |
| Change colours or fonts                   | `src/app/globals.css` (`@theme` block)                                                           |
| Allow another file type or a bigger limit | `siteConfig.upload` in `src/config/site.ts`                                                      |
| Follow a change in the backend JSON       | `features/workspace/api/types.ts` and `types.ts`; TypeScript flags the rest                      |
| Add a new kind of state change            | Add an action to `workspace-reducer.ts`, a test next to it, then an action in `use-workspace.ts` |
| Add a new page                            | Create `src/app/<route>/page.tsx` and set `available: true` in `siteConfig.nav`                  |

## Backend contract

JSON uses camelCase (in FastAPI: Pydantic `alias_generator=to_camel`). Full types are in
`src/features/workspace/api/types.ts` and `src/features/workspace/types.ts`.

| Method & path              | Request                          | Response                     |
| -------------------------- | -------------------------------- | ---------------------------- |
| `POST /chat`               | `{ question, fileIds, history }` | `AskResponse` (see below)    |
| `POST /documents`          | multipart form, field `file`     | `{ id, status: FileStatus }` |
| `GET /documents/{id}`      | –                                | `{ id, status: FileStatus }` |
| `POST /documents/{id}/ocr` | –                                | `{ id, status: FileStatus }` |

`AskResponse`:

```jsonc
{
  "content": "Keep it between **2 °C and 8 °C** [1].", // markdown; [n] must match a source index
  "grounded": true,
  "followUps": ["Show form QA-07 fields"],
  "run": {
    "totalMs": 3800,
    "steps": [{ "id": "s1", "node": "router", "summary": "…", "durationMs": 400, "status": "done" }],
  },
  "sources": [
    {
      "index": 1,
      "fileId": "doc_123",
      "fileName": "SOP_Cold_Chain_v3.pdf",
      "location": "Section 4.2 · page 7 of 18",
      "heading": "4.2 Last-mile temperature control",
      "score": 0.91,
      "passages": [{ "text": "…", "cited": true }],
    },
  ],
}
```

`FileStatus` is one of `uploading` (`progress` 0–1), `processing` (`stage`: parsing | chunking | embedding |
indexing, optional `progress`), `ready` (`pages`, `chunks`) or `failed` (`reason`, optional `recovery`: ocr | retry).

The browser calls the backend directly, so the FastAPI app must allow the frontend's origin with CORS.

## Not built yet

- Streaming answers token by token (the API returns the whole answer at once)
- Loading the file list and past chats from the backend (the demo starts from sample data)
- Sending answer feedback (thumbs up/down are local only)
- The Agents, Evaluations and How it works pages (shown as "Soon" in the nav)
