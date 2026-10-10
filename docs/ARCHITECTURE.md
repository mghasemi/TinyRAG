# TinyRAG — Architecture

## 1. System Overview

TinyRAG is a self-hosted Retrieval-Augmented Generation (RAG) application.
Users upload documents (`.txt`, `.md`, `.pdf`), the backend extracts and
chunks the text, embeds each chunk into a vector store (ChromaDB), and
answers questions by retrieving the most relevant chunks and feeding them
to an LLM as context.

```
┌──────────────────────────────┐         ┌──────────────────────────────┐
│        Frontend (3500)       │         │        Backend (8500)        │
│  React 18 + TypeScript       │  HTTP   │  FastAPI + Uvicorn (Py3.11)  │
│  Vite dev server             │ ──────► │                              │
│  Tailwind CSS                │  proxy  │  ┌────────────────────────┐  │
│                              │         │  │ app/main.py (routes)  │  │
│  ┌────────────────────────┐  │         │  └──────┬─────────┬──────┘  │
│  │ UploadSection          │  │         │         │         │         │
│  │ DocumentBrowser        │  │         │  ┌──────▼──┐  ┌───▼───────┐ │
│  │ QASection              │  │         │  │ ingest  │  │  llm      │ │
│  │ CollectionManager      │  │         │  │ (extract│  │ (stream   │ │
│  │ SettingsSection        │  │         │  │  chunk) │  │  OpenAI)  │ │
│  └────────────────────────┘  │         │  └────┬─────┘  └───┬───────┘ │
└──────────────┬───────────────┘         │       │            │         │
               │                         │  ┌────▼────────────▼───────┐  │
               │                         │  │ chromadb_service.py     │  │
               │                         │  │ (embed + vector store)  │  │
               │                         │  └────┬───────────────┬────┘  │
               │                         │       │               │       │
               │                         │  ┌────▼────┐     ┌────▼─────┐ │
               │                         │  │ SQLite  │     │ ChromaDB │ │
               │                         │  │ (meta)  │     │ (vectors)│ │
               │                         │  └─────────┘     └──────────┘ │
               │                         └──────────────────────────────┘
               │
               └─── MCP server (stdio) → talks to backend HTTP API
```

## 2. Containers & Ports

| Service  | Image base        | Port (host) | Purpose                        |
|----------|-------------------|-------------|--------------------------------|
| backend  | `python:3.11-slim`| **8500**    | FastAPI application + ChromaDB |
| frontend | `node:20-alpine`  | **3500**    | Vite dev server + React SPA    |

Both containers are managed by a single `docker-compose.yml`. The backend
restarts automatically (`restart: unless-stopped`); the frontend `depends_on`
the backend but does not wait for health — the UI degrades gracefully while
the backend warms up.

## 3. Backend Modules

| File                    | Responsibility |
|-------------------------|----------------|
| `app/main.py`           | FastAPI app: routes, CORS, startup migration, SSE streaming |
| `app/settings.py`       | Runtime config: reads env defaults, persists overrides to `llm_config.json` |
| `app/chromadb_service.py` | Multi-collection ChromaDB service + embedding function |
| `app/ingest.py`         | Text extraction (PyMuPDF for PDFs) + chunking algorithm |
| `app/llm.py`            | Streaming OpenAI-compatible chat completions (httpx) |
| `app/database.py`       | SQLAlchemy engine + session factory (SQLite) |
| `app/models.py`         | ORM models: `Document`, `QueryLog` |

### 3.1 Request path for `/qa` (streaming)

1. `POST /qa` receives `{"question": "..."}`.
2. `qa_stream()` calls `chroma.query(question, n_results=5)` against the
   **active collection**.
3. Retrieved chunks are formatted into a prompt by `llm.build_prompt()`.
4. `llm.stream_response()` POSTs to `{base_url}/chat/completions` with
   `stream: true`, then yields each token as a JSON line.
5. `main.py` wraps the generator in an SSE frame (`data: {json}\n\n`) via
   `StreamingResponse(media_type="text/event-stream")`.
6. A final `{"sources": [...]}` message and `[DONE]` terminate the stream.

### 3.2 Runtime settings (no restart needed)

The LLM provider (model, base URL, API key) and the active collection are
persisted in `/app/data/llm_config.json`. `GET/POST /settings` and
`GET/POST /collections/active` read/write this file at runtime. Env vars
set at container start act as defaults; file values override them.

## 4. Frontend Components

| Component            | Purpose |
|----------------------|---------|
| `App.tsx`            | Shell: header, tab nav (Chat / Settings), collection manager |
| `UploadSection.tsx`  | Drag-and-drop + click upload → `POST /ingest` |
| `DocumentBrowser.tsx`| Lists docs in active collection; delete button per doc |
| `QASection.tsx`      | Chat UI consuming the `/qa` SSE stream |
| `CollectionManager.tsx` | Dropdown: switch active collection, create new one |
| `SettingsSection.tsx`| Edit model / base URL / API key at runtime |

### 4.1 Same-origin proxy (why drag-and-drop works)

The frontend runs on port 3500 but talks to the backend on 8500. Instead of
relying on CORS, `vite.config.ts` defines a **dev-server proxy**:

- `VITE_API_URL` is empty in `docker-compose.yml`, so every component builds
  relative URLs (`/ingest`, `/qa`, …).
- Vite forwards those paths to `http://backend:8500` (the Docker service
  name) with `changeOrigin: true`.

Result: the browser sees only same-origin requests to `localhost:3500`, so
no CORS preflight is involved — this is what fixed the original
"Failed to fetch" drag-and-drop error.

## 5. Persistence (Docker volumes)

| Volume          | Mount          | Contents                          |
|-----------------|----------------|-----------------------------------|
| `sqlite_data`   | `/app/data`    | `rag.db` (SQLite) + `llm_config.json` |
| `chromadb_data` | `/app/data/chroma` | ChromaDB vector store (per-collection) |
| `uploads`       | `/app/uploads` | Staging area; files removed after ingest |

Volumes are **named**, so `docker compose down` does not destroy data.
Only `docker compose down -v` removes it.

## 6. Key Design Decisions

1. **CPU-only PyTorch**: the backend Dockerfile installs `torch` from the
   CPU wheel index *before* `requirements.txt`, avoiding ~1.3 GB of CUDA
   bloat while still supporting `sentence-transformers`.
2. **`all-MiniLM-L6-v2` embeddings**: 384-dim, ~22 MB — fast enough to run
   on a laptop CPU at ingest time.
3. **Chunking**: 500 chars with 50-char overlap, sentence-aware break
   points (see `docs/DATA_FLOW.md`).
4. **Manual SSE framing**: `qa_stream()` yields plain JSON strings; the
   `StreamingResponse` wrapper adds `data: ` framing. Using
   `sse-starlette`'s `EventSourceResponse` caused a double `data:` prefix.
5. **Metadata-driven deletion**: each chunk stores its source filename in
   ChromaDB metadata, so deleting a document is a metadata-filtered
   `collection.delete(ids=...)`.
