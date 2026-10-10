# TinyRAG — Data Flow & Algorithms

This document describes the processing pipeline in detail: ingestion,
chunking, embedding, retrieval, and answer generation.

---

## 1. Ingestion Pipeline

```
Uploaded file
     │
     ▼
┌───────────────────────────┐
│ 1. Validate extension     │  .txt / .md / .pdf only
└───────────────────────────┘
     │
     ▼
┌───────────────────────────┐
│ 2. Persist to /app/uploads│  uuid_hex + original filename
└───────────────────────────┘
     │
     ▼
┌───────────────────────────┐
│ 3. Extract text           │  txt/md: read bytes as UTF-8
│                           │  pdf:   PyMuPDF page.get_text()
└───────────────────────────┘
     │
     ▼
┌───────────────────────────┐
│ 4. Chunk text             │  500 chars, 50 overlap (see §2)
└───────────────────────────┘
     │
     ▼
┌───────────────────────────┐
│ 5. Embed chunks           │  all-MiniLM-L6-v2 → 384-dim vectors
└───────────────────────────┘
     │
     ▼
┌───────────────────────────┐
│ 6. Store in ChromaDB      │  active collection, cosine space
└───────────────────────────┘
     │
     ▼
┌───────────────────────────┐
│ 7. Log metadata in SQLite │  Document row: filename, size,
│                           │  chunk_count, collection, safe_name
└───────────────────────────┘
     │
     ▼
   temp file removed
```

**Chunk IDs** are deterministic: `sha256("{safe_name}:{chunk_index}")[:16]`.
This means re-ingesting the same file produces the same chunk IDs — useful
for idempotent deletion (see §5).

**Metadata stored per chunk** (in ChromaDB):

```json
{"filename": "<uuid>_original.pdf", "chunk_index": 3, "collection": "Default"}
```

---

## 2. Chunking Algorithm

`backend/app/ingest.py` — `chunk_text()`

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `CHUNK_SIZE`    | 500 chars | Balances retrieval precision vs. LLM context |
| `CHUNK_OVERLAP` | 50 chars  | Preserves sentence context across chunk boundaries |

Algorithm (per chunk):

1. Take the next 500 characters starting at `start`.
2. If not at the end of the text, search **backwards** from the end for the
   first "good" break point, in priority order:
   - `". "` (sentence end)
   - `"\n\n"` (paragraph end)
   - `"\n"` (line end)
   - `"  "` (double space)
   The break must be at least `CHUNK_OVERLAP` (50) chars in, otherwise the
   chunk would be too small.
3. Trim the chunk at that break point.
4. Advance `start = end - CHUNK_OVERLAP`, so chunks overlap by 50 chars.
5. Drop empty chunks.

**Effect:** each chunk is a self-contained unit that usually ends at a
sentence boundary, improving both embedding quality and answer quality.

---

## 3. Embeddings

- **Model:** `sentence-transformers/all-MiniLM-L6-v2`
- **Dimensions:** 384
- **Normalization:** `normalize_embeddings=True` (unit vectors)
- **Distance metric:** cosine (`hnsw:space: "cosine"` in collection metadata)

The same embedding function is used for both ingest and query, which is
required for meaningful similarity scores.

---

## 4. Retrieval & Answer Generation (RAG)

```
User question
     │
     ▼
┌───────────────────────────┐
│ chroma.query(question, 5) │  embed question → cosine top-5
└───────────────────────────┘
     │
     ▼  chunks + metadata
┌───────────────────────────┐
│ build_prompt()            │  formats sources + question
└───────────────────────────┘
     │
     ▼
┌───────────────────────────┐
│ stream_response()         │  POST {base_url}/chat/completions
│                           │  stream=true, temperature=0.3
└───────────────────────────┘
     │
     ▼  SSE tokens
   frontend renders
```

### 4.1 Prompt template (`llm.build_prompt`)

```
You are a helpful AI assistant. Answer the user's question based ONLY on the
provided context documents below. If the context does not contain enough
information, say so clearly.

=== Context Documents ===
[Source 1: <filename> (chunk <idx>)]
<chunk text>

[Source 2: <filename> (chunk <idx>)]
<chunk text>

=== End of Context ===

Question: <question>

Answer:
```

### 4.2 LLM request payload

```json
{
  "model": "<configured model>",
  "messages": [
    {"role": "system", "content": "You are a helpful RAG assistant. Answer based on the provided context."},
    {"role": "user", "content": "<prompt>"}
  ],
  "stream": true,
  "temperature": 0.3,
  "max_tokens": 2048
}
```

- **temperature 0.3** — low creativity, answers stay grounded in context.
- **max_tokens 2048** — enough for detailed answers without runaway output.
- **timeout 120s** — generous for slow local models (LM Studio, Ollama).

### 4.3 SSE protocol

The backend yields raw JSON strings from `llm.stream_response()`; the route
wrapper adds `data: ` framing:

```
data: {"token": "..."}
data: {"done": true, "full_response": "..."}
data: {"sources": ["..."]}
data: [DONE]
```

The frontend accumulates `token` fields as they arrive and updates the chat
bubble live.

---

## 5. Deletion Semantics

`DELETE /documents/{id}`:

1. Look up the `Document` row in SQLite → gives `chroma_doc_id` (the
   `safe_name` = `uuid_originalname`).
2. `chroma.delete_by_filename(safe_name)`:
   - `collection.get(where={"filename": safe_name})` → all chunk IDs
   - `collection.delete(ids=...)` → remove vectors
3. `db.delete(doc)` + commit → remove the SQLite row.

If the ChromaDB chunk set is empty (e.g. manually removed), deletion still
succeeds for the SQLite row.

---

## 6. Multi-Collection Isolation

Collections are fully isolated namespaces in ChromaDB:

- `ingest` writes to the active collection only.
- `documents` lists rows whose `collection` column matches the active one.
- `qa` retrieves from the active collection only.
- `DELETE` removes chunks from the collection that holds them.

The active collection name is persisted in `llm_config.json`, so switching
collections survives a container restart.

---

## 7. Failure Modes

| Failure | Behavior |
|---------|----------|
| LLM endpoint unreachable | SSE stream emits `{"error": "LLM API returned ..."}`; frontend shows error in chat bubble |
| No API key configured | Provider returns 401; surfaced as `error` message |
| No relevant chunks found | Stream emits a single "No relevant documents found..." token, then `[DONE]` |
| Unreadable PDF (scanned) | Ingest returns 400 "Extracted text is empty" |
| Backend down at startup | Frontend components show empty states; no crash |
