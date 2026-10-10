# TinyRAG — REST API Reference

Base URL: `http://localhost:8500` (inside Docker: `http://backend:8500`)

All endpoints return JSON except `/qa`, which returns a Server-Sent Events
(SSE) stream.

---

## Health

### `GET /health`

Returns service health and collection stats.

```bash
curl http://localhost:8500/health
```

**Response 200:**
```json
{
  "status": "ok",
  "active_collection": "Default",
  "collections": [
    {"name": "Default", "doc_count": 112},
    {"name": "Research", "doc_count": 12}
  ]
}
```

---

## Ingest

### `POST /ingest` — multipart/form-data

Upload one document. Supported: `.txt`, `.md`, `.pdf`.

```bash
curl -X POST http://localhost:8500/ingest \
  -F "file=@/path/to/paper.pdf"
```

**Response 200:**
```json
{
  "status": "ok",
  "document_id": 42,
  "filename": "paper.pdf",
  "file_type": "pdf",
  "file_size": 482193,
  "chunk_count": 17,
  "collection": "Default"
}
```

The document is ingested into the **currently active collection**.

**Errors:**
- `400` — unsupported file type (`.docx`, `.png`, …)
- `400` — extracted text is empty (e.g. scanned PDF without OCR)

---

## Documents

### `GET /documents`

Lists documents in the **active collection**, newest first.

```bash
curl http://localhost:8500/documents
```

**Response 200:**
```json
[
  {
    "id": 42,
    "filename": "paper.pdf",
    "file_type": "pdf",
    "file_size": 482193,
    "upload_timestamp": "2026-07-08T06:15:00.123456",
    "chunk_count": 17,
    "collection": "Default"
  }
]
```

### `DELETE /documents/{id}`

Deletes a document from SQLite **and** removes its chunks from ChromaDB.

```bash
curl -X DELETE http://localhost:8500/documents/42
```

**Response 200:**
```json
{"status": "ok", "deleted_id": 42, "filename": "paper.pdf"}
```

**Errors:**
- `404` — document id not found

---

## QA (streaming)

### `POST /qa`

Ask a question. The response is an SSE stream of JSON lines.

```bash
curl -N -X POST http://localhost:8500/qa \
  -H "Content-Type: application/json" \
  -d '{"question": "What is deep learning?"}'
```

**Stream format:**

```
data: {"token": "\n\n"}
data: {"token": "Based"}
data: {"token": " on"}
...
data: {"done": true, "full_response": "Based on the provided context, ..."}
data: {"sources": ["2b8166105d1d4fd3b9eaacd62ad1572a_paper.pdf"]}
data: [DONE]
```

**Message types:**

| Field(s)             | Meaning |
|----------------------|---------|
| `token`              | One streamed token of the answer |
| `done` + `full_response` | Final accumulated answer |
| `sources`            | Deduplicated source filenames used as context |
| `error`              | LLM API error (e.g. 401, connection refused) |
| `[DONE]`             | Terminator — stream is complete |

**Request body:**
- `question` (string, required)
- `collection` (string, optional) — switches active collection before querying

---

## Settings

### `GET /settings`

Returns the current LLM provider config. **The API key is masked.**

```bash
curl http://localhost:8500/settings
```

**Response 200:**
```json
{
  "base_url": "http://192.168.1.81:1234/v1",
  "model": "ornith-1.0-35b_moe",
  "api_key": "not-need...",
  "active_collection": "Default"
}
```

### `POST /settings`

Update model, base URL, and/or API key. Values persist to
`/app/data/llm_config.json` and take effect immediately — no restart.

```bash
curl -X POST http://localhost:8500/settings \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4o-mini", "base_url": "https://api.openai.com/v1", "api_key": "sk-..."}'
```

Any subset of `{model, base_url, api_key}` is accepted. The response is the
same shape as `GET /settings`.

---

## Collections

### `GET /collections`

List all collections with doc counts, plus the active one.

```bash
curl http://localhost:8500/collections
```

**Response 200:**
```json
{
  "collections": [
    {"name": "Default", "doc_count": 112},
    {"name": "Research", "doc_count": 12}
  ],
  "active": "Default"
}
```

### `POST /collections`

Create a new (empty) collection.

```bash
curl -X POST http://localhost:8500/collections \
  -H "Content-Type: application/json" \
  -d '{"name": "Research"}'
```

**Response 200:**
```json
{"status": "ok", "collection": {"name": "Research", "doc_count": 0}}
```

**Errors:**
- `400` — name missing or contains non-alphanumeric chars
- `409` — collection already exists

### `GET /collections/active`

```bash
curl http://localhost:8500/collections/active
```

**Response 200:**
```json
{"name": "Default", "doc_count": 112}
```

### `POST /collections/active`

Switch the active collection. Persists across restarts.

```bash
curl -X POST http://localhost:8500/collections/active \
  -H "Content-Type: application/json" \
  -d '{"name": "Research"}'
```

**Response 200:**
```json
{"status": "ok", "name": "Research", "doc_count": 12}
```

**Errors:**
- `400` — name missing
- `404` — collection does not exist

---

## Interactive Docs

FastAPI auto-generates OpenAPI docs at:

- Swagger UI: `http://localhost:8500/docs`
- ReDoc: `http://localhost:8500/redoc`
- OpenAPI JSON: `http://localhost:8500/openapi.json`
