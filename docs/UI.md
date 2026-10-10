# TinyRAG — Frontend Guide

## 1. Layout

The UI is a single-page React app served by Vite on port 3500.

```
┌──────────────────────────────────────────────────────────────┐
│  [📚 Tiny RAG]   [Chat] [Settings]   [Collections ▾]  backend: │
├──────────────────────────────────────────────────────────────┤
│  ┌───────────────────┐  ┌──────────────────────────────────┐ │
│  │ Upload Documents  │  │  Ask Your Documents              │ │
│  │  (drag & drop)    │  │  ┌────────────────────────────┐  │ │
│  ├───────────────────┤  │  │ user bubble                │  │ │
│  │ Knowledge Base    │  │  │ assistant bubble + sources │  │ │
│  │  doc list w/      │  │  └────────────────────────────┘  │ │
│  │  delete buttons   │  │  [input........................] │ │
│  └───────────────────┘  │  [Send]                          │ │
│                         └──────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

## 2. Chat tab (default)

**Left column:**
- **Upload Documents** — click to open a file picker, or drag & drop files
  onto the dashed area. Supports multiple files. Each upload POSTs to
  `/ingest`; the status line shows success (chunk count + size) or failure.
- **Knowledge Base** — lists documents in the *active collection*, newest
  first. Each row shows an icon by type (📄 pdf, 📝 md, 📃 txt), size,
  chunk count, and upload time. Hovering a row reveals a **trash button**
  that deletes the document (SQLite + ChromaDB).

**Right column (Ask Your Documents):**
- Type a question, press **Send** (or Enter).
- The assistant's answer streams in token-by-token (SSE).
- When complete, a "📚 Sources referenced" block lists the source filenames
  that were retrieved for the answer.
- Markdown-lite formatting: `**bold**`, `` `code` ``, line breaks.

## 3. Settings tab

Opens the **LLM Provider Settings** form (single centered card):

| Field | Notes |
|-------|-------|
| Model | e.g. `gpt-4o-mini`, `ornith-1.0-35b_moe` |
| Base URL | OpenAI-compatible endpoint, must end in `/v1` |
| API Key | Password field; masked in GET responses (`sk-abc...`) |

**Save Settings** POSTs to `/settings`. Changes apply immediately — no
container restart. A success/error banner confirms the result. The API key
may be left empty for providers that don't require auth (LM Studio, Ollama).

## 4. Collection Manager (header dropdown)

The **Collections** button in the header shows the active collection name
and its document count. Clicking opens a dropdown:

- List of all collections (active one highlighted in blue).
- Doc count per collection.
- Click a collection to **switch** — the knowledge base list and QA query
  immediately target the new collection.
- **Create new:** type a name in the input and press `+` or Enter. The new
  collection is created and automatically activated.
- Names must be alphanumeric (spaces allowed).

## 5. Network Layer

All components share this pattern:

```ts
const API_URL = import.meta.env.VITE_API_URL || '';
fetch(`${API_URL}/ingest`, { method: 'POST', body: formData });
```

- `VITE_API_URL` is empty in Docker, so requests go **same-origin** to the
  Vite dev server (port 3500).
- Vite's proxy forwards known API paths to `http://backend:8500`.
- The QA section reads the SSE stream with `ReadableStream` + `TextDecoder`,
  splitting on newlines and parsing `data: {json}` lines.

## 6. State & Refresh

- `App.tsx` holds a `refreshKey` used as `key` on `DocumentBrowser`; it
  increments after an ingest completes or the collection switches, forcing
  a refetch.
- `DocumentBrowser` also refetches internally after a delete.
- `CollectionManager` refetches its list after create/switch.
