# TinyRAG — Operations Guide

## 1. Prerequisites

- Docker Engine 20.10+ and Docker Compose v2
- An OpenAI-compatible LLM endpoint. Options:
  - **Cloud:** OpenAI (`https://api.openai.com/v1`) with an API key
  - **Local:** LM Studio, Ollama, vLLM, llama.cpp server — any URL ending
    in `/v1` that implements `/chat/completions`

## 2. Quick Start

```bash
cd /home/mehdi/Code/Python/TinyRAG

# Optional: preconfigure the LLM provider (compose defaults otherwise)
cat > .env <<'EOF'
LLM_BASE_URL=http://192.168.1.81:1234/v1
LLM_API_KEY=not-needed
LLM_MODEL=ornith-1.0-35b_moe
EOF

docker compose up -d --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3500 |
| Backend health | http://localhost:8500/health |
| API docs | http://localhost:8500/docs |

> The `.env` file is picked up automatically by Docker Compose for the
> `${VAR:-default}` substitutions in `docker-compose.yml`. The same values
> can also be edited at runtime in the UI (Settings tab) — those overrides
> are stored in `/app/data/llm_config.json` and take precedence.

## 3. Configuration Reference

### 3.1 Environment variables (compose)

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_BASE_URL` | `https://api.openai.com/v1` | LLM API base URL |
| `LLM_API_KEY` | *(empty)* | API key for the LLM provider |
| `LLM_MODEL` | `gpt-4o-mini` | Model name |
| `DATABASE_URL` | `sqlite:///app/data/rag.db` | SQLAlchemy URL |
| `CHROMA_PATH` | `/app/data/chroma` | ChromaDB persistence dir |
| `UPLOAD_DIR` | `/app/uploads` | Temp upload staging |
| `VITE_API_URL` | *(empty)* | Frontend → backend URL; empty = same-origin via Vite proxy |

### 3.2 Runtime settings (UI / API)

Stored in `/app/data/llm_config.json` (on the `sqlite_data` volume):

| Key | Description |
|-----|-------------|
| `model` | Active LLM model |
| `base_url` | Active LLM endpoint |
| `api_key` | Active API key |
| `active_collection` | Current ChromaDB collection |

Editable via the **Settings** tab or `GET/POST /settings`, and the
**Collections** dropdown or `GET/POST /collections/active`.

## 4. Common Operations

### View logs

```bash
docker compose logs -f backend
docker compose logs -f frontend
```

### Rebuild after code changes

```bash
docker compose build backend frontend
docker compose up -d
```

### Reset everything (destroys data)

```bash
docker compose down -v
```

### Start fresh with only default collection

```bash
docker compose down -v
docker compose up -d --build
# The backend auto-creates the "Default" collection on first boot.
```

## 5. Data Locations

| Volume | Host-invisible, named | Contents |
|--------|----------------------|----------|
| `sqlite_data` | yes | `/app/data/rag.db`, `/app/data/llm_config.json` |
| `chromadb_data` | yes | `/app/data/chroma/*` |
| `uploads` | yes | transient files, auto-removed after ingest |

To back up: `docker run --rm -v tinyrag_sqlite_data:/data -v "$PWD":/backup alpine tar czf /backup/sqlite.tgz -C /data .` (repeat for each volume).

## 6. Security Notes

- The backend CORS allows `*` — fine for local use; do not expose port 8500
  directly to the internet.
- The API key is stored **in plaintext** in `llm_config.json` and masked
  (`sk-abc...`) in API responses. The full key is only sent to the
  configured LLM endpoint.
- The frontend runs a dev-mode Vite server. For production, build the SPA
  (`npm run build`) and serve statically behind a reverse proxy.

## 7. Troubleshooting

### Backend won't start / crash-loops

```bash
docker compose logs backend | tail -50
```

Common causes:
- Port 8500 already in use: `ss -tlnp | grep 8500`
- Corrupt ChromaDB: delete the `chromadb_data` volume and re-ingest
- Missing `collection`/`chroma_doc_id` column in SQLite — the startup
  migration in `main.py` adds them automatically (it runs
  `ALTER TABLE ... ADD COLUMN` in a try/except).

### QA returns "LLM API returned 401"

The API key is missing/invalid. Fix via the **Settings** tab, or:

```bash
curl -X POST http://localhost:8500/settings \
  -H "Content-Type: application/json" \
  -d '{"api_key": "sk-...", "base_url": "https://api.openai.com/v1"}'
```

### Drag-and-drop upload fails with "Failed to fetch"

This was a CORS/absolute-URL issue, fixed by the Vite same-origin proxy.
If it recurs:
1. Confirm `VITE_API_URL` is empty in `docker-compose.yml`.
2. Rebuild the frontend: `docker compose build frontend && docker compose up -d frontend`.
3. Confirm the proxy target works: `docker exec tinyrag-frontend wget -qO- http://backend:8500/health`.

### Frontend shows "Internal Server Error" on ingest

Check backend logs — historically this was a missing `chroma_doc_id`
column. Ensure the backend image is rebuilt after model changes:
`docker compose build backend && docker compose up -d backend`.

### QA answer shows "[object Object]"

Stale frontend build with the old JSX→string rendering bug. Rebuild the
frontend image and hard-refresh the browser (Ctrl+Shift+R).

## 8. Project Layout

```
TinyRAG/
├── docker-compose.yml
├── .env                      # compose variable defaults (LLM provider)
├── mcp_server.py             # MCP server for AI agents
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py           # routes, CORS, SSE, startup migration
│       ├── settings.py       # runtime config (llm_config.json)
│       ├── chromadb_service.py
│       ├── ingest.py         # extraction + chunking
│       ├── llm.py            # streaming chat completions
│       ├── database.py
│       └── models.py
├── frontend/
│   ├── Dockerfile
│   ├── vite.config.ts        # dev server + API proxy
│   └── src/
│       ├── App.tsx
│       └── components/
│           ├── UploadSection.tsx
│           ├── DocumentBrowser.tsx
│           ├── QASection.tsx
│           ├── CollectionManager.tsx
│           └── SettingsSection.tsx
└── docs/
    ├── ARCHITECTURE.md
    ├── API.md
    ├── DATA_FLOW.md
    ├── UI.md
    ├── MCP.md
    └── OPERATIONS.md
```
