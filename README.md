# Tiny RAG

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](backend/Dockerfile)
[![Node.js](https://img.shields.io/badge/Node.js-20-43861d?logo=nodejs&logoColor=white)](frontend/Dockerfile)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](docker-compose.yml)

A lightweight, self-hosted **Retrieval-Augmented Generation (RAG)** system:
upload documents, ask questions, get grounded answers. Built with FastAPI,
React, ChromaDB, and Docker Compose.

## Features

- 📄 **Multi-format ingestion** — `.txt`, `.md`, `.pdf` (PyMuPDF)
- 🗂️ **Multi-collection vector store** — create, switch, and isolate
  collections (default collection: `Default`)
- 💬 **Streaming QA** — SSE token-by-token answers with source references
- ⚙️ **Runtime LLM settings** — switch model / base URL / API key from the
  UI, no restart needed
- 🗑️ **Document deletion** — removes metadata + vectors in one click
- 🤖 **MCP server** — query your documents from AI agents (Hermes, Claude,
  Cursor) via `mcp_server.py`
- 🖥️ **Drag-and-drop upload** with same-origin Vite proxy (no CORS pain)

## Quick Start

```bash
cd TinyRAG

# Optional: preconfigure an LLM provider (defaults to OpenAI gpt-4o-mini)
cat > .env <<'EOF'
LLM_BASE_URL=http://you-model-provider
LLM_API_KEY=your-api-key
LLM_MODEL=model-id
EOF

docker compose up -d --build
```

| Service  | URL                        |
| -------- | -------------------------- |
| Frontend | http://localhost:3500      |
| Backend  | http://localhost:8500      |
| API docs | http://localhost:8500/docs |

## Documentation

| Doc                                         | Contents                                       |
| ------------------------------------------- | ---------------------------------------------- |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System overview, modules, design decisions     |
| [docs/API.md](docs/API.md)                   | Complete REST API reference                    |
| [docs/DATA_FLOW.md](docs/DATA_FLOW.md)       | Ingestion, chunking, retrieval, RAG algorithms |
| [docs/UI.md](docs/UI.md)                     | Frontend components & behavior                 |
| [docs/MCP.md](docs/MCP.md)                   | MCP server + AI agent integration              |
| [docs/OPERATIONS.md](docs/OPERATIONS.md)     | Deployment, config, troubleshooting            |

## Tech Stack

| Layer         | Technology                                     |
| ------------- | ---------------------------------------------- |
| Backend       | Python 3.11, FastAPI, Uvicorn                  |
| Frontend      | React 18, TypeScript, Tailwind CSS, Vite       |
| Vector DB     | ChromaDB (persistent, multi-collection)        |
| Relational    | SQLite3 via SQLAlchemy ORM                     |
| Embeddings    | sentence-transformers/all-MiniLM-L6-v2 (384-d) |
| PDF parsing   | PyMuPDF (fitz)                                 |
| LLM           | Any OpenAI-compatible API (configurable)       |
| Orchestration | Docker Compose                                 |
| Agent bridge  | MCP server (mcp_server.py)                     |

## Repository Layout

```
TinyRAG/
├── docker-compose.yml
├── .env                       # LLM provider defaults
├── mcp_server.py              # MCP server for AI agents
├── backend/
│   ├── Dockerfile             # CPU-only PyTorch (~200 MB)
│   ├── requirements.txt
│   └── app/
│       ├── main.py            # FastAPI routes + SSE
│       ├── settings.py        # runtime config
│       ├── chromadb_service.py# multi-collection vector store
│       ├── ingest.py          # extraction + chunking
│       ├── llm.py             # streaming LLM calls
│       ├── database.py        # SQLAlchemy engine
│       └── models.py          # Document, QueryLog
├── frontend/
│   ├── Dockerfile
│   ├── vite.config.ts         # dev server + API proxy
│   └── src/
│       ├── App.tsx
│       └── components/
│           ├── UploadSection.tsx
│           ├── DocumentBrowser.tsx
│           ├── QASection.tsx
│           ├── CollectionManager.tsx
│           └── SettingsSection.tsx
└── docs/                      # detailed documentation
```

## Agent notes

Notes for AI agents working on this repo (moved out of agent memory, 2026-10):

- **Vite proxy target**: the frontend dev server proxies API calls to `backend:8500` — a Docker *service name*, not localhost. Outside Compose these requests fail by design.
- **Runtime LLM settings** live in `app/settings.py`, persisted as `llm_config.json` on a volume; changes from the UI survive restarts without rebuilds.
- **SSE streaming**: use FastAPI `StreamingResponse`, *not* `EventSourceResponse` — the latter double-prefixes `data:` lines and breaks the client parser.
- **ChromaDB document deletion pattern**: no single delete-by-filename call; do `get(where={"filename": ...}) → collect IDs → delete(ids=...)` (implemented as `delete_by_filename`).
- **Dockerfiles** pre-install CPU-only PyTorch (~200 MB) to keep the image small and avoid CUDA bloat.
