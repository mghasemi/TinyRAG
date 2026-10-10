**Root**
```
tinyrag/
├── docker-compose.yml
├── .gitignore
├── README.md
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── __init__.py
│       ├── main.py              # FastAPI app, routes, CORS
│       ├── database.py          # SQLAlchemy engine + SessionLocal
│       ├── models.py            # Document, QueryLog tables
│       ├── chromadb_service.py  # ChromaDB client, embed, query
│       ├── ingest.py            # text extraction + chunking
│       └── llm.py               # streaming LLM call
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── components/
│       │   ├── UploadSection.tsx
│       │   ├── DocumentBrowser.tsx
│       │   └── QASection.tsx
│       └── index.css
├── data/
│   ├── sqlite/                  # volume mount for SQLite
│   └── chromadb/                # volume mount for ChromaDB
└── uploads/                     # volume mount for temp uploads
```

**Key design decisions:**
- **Embeddings**: `sentence-transformers/all-MiniLM-L6-v2` (lightweight, ~22 MB, 384-dim)
- **LLM**: OpenAI-compatible API (configurable via `LLM_BASE_URL` + `LLM_API_KEY` env vars)
- **Frontend server**: Vite dev server in Docker (port 3500), nginx reverse proxy for production
- **Chunking**: 500-char chunks with 50-char overlap
- **CORS**: Frontend (3500) → backend (8500) allowed
