# TinyRAG — MCP Server & Agent Integration

TinyRAG ships with a Model Context Protocol (MCP) server that exposes the
document-query backend to AI agents (Hermes, Claude, Cursor, etc.). The
server talks to the backend over its HTTP API, so it needs no ML
dependencies — just `mcp` and `httpx`.

## 1. Overview

```
Agent (Hermes)  ──stdio──►  mcp_server.py  ──HTTP──►  TinyRAG backend :8500
                              (tools)                    (collections + QA)
```

Tools exposed:

| Tool | Description |
|------|-------------|
| `list_collections` | List all collections with document counts |
| `query_collection` | Ask a question; returns RAG answer + source filenames |
| `search_chunks` | Retrieve raw context chunks without LLM generation |

## 2. Requirements

- Python 3.10+ with `mcp` and `httpx`:

```bash
pip install "mcp>=1.0" httpx
```

- The TinyRAG backend reachable at `http://localhost:8500` (override with
  the `TINYRAG_URL` env var).

## 3. Running Standalone

```bash
python /home/mehdi/Code/Python/TinyRAG/mcp_server.py
```

The server speaks JSON-RPC over stdio. A quick manual probe:

```bash
printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"x","version":"1"}}}\n' \
  | python mcp_server.py
```

## 4. Registering with Hermes

```bash
hermes mcp add tinyrag \
  --command python \
  --args /home/mehdi/Code/Python/TinyRAG/mcp_server.py
```

Verify:

```bash
hermes mcp list     # shows tinyrag, tools=all, enabled
hermes mcp test tinyrag
```

> Note: the `hermes mcp add` flow may report "connected but reported no
> tools" during the one-shot probe — this is a known registration timing
> quirk. The tools *are* discovered once a real session connects (verified
> via a direct JSON-RPC probe: 3 tools listed).

The registration enables the three tools as first-class tools in future
Hermes sessions (tool changes take effect on a new session).

## 5. Using the Skill

A companion skill, **`tinyrag-search`**, is installed at:

```
~/.hermes/profiles/coder/skills/tinyrag-search/SKILL.md
```

It tells the agent:

- When to reach for `list_collections` (browse what's available).
- When to use `query_collection` (answer a question grounded in documents).
- When to use `search_chunks` (inspect raw context without LLM cost).
- Example prompts mapping user requests to tool calls.

## 6. Tool Semantics

### `list_collections`

No arguments. Returns lines like:

```
Collections:
  • Default — 112 document(s)
  • Research — 12 document(s)
```

### `query_collection(question, collection?, n_results?)`

- `question` (required): the natural-language question.
- `collection` (optional): target collection. If omitted, uses the backend's
  currently active collection (which the UI may have changed).
- `n_results` (optional, default 5): number of context chunks.

Behavior: optionally switches the active collection, POSTs to `/qa`, parses
the SSE stream, and returns:

```
<answer text>

--- Sources ---
  • paper.pdf
  • notes.md
```

### `search_chunks(question, collection?, n_results?)`

Same parameters, but returns the raw retrieved tokens (the context only) —
no LLM call, no answer. Useful for debugging what a collection contains.

## 7. Configuration

| Env var | Default | Purpose |
|---------|---------|---------|
| `TINYRAG_URL` | `http://localhost:8500` | Backend base URL |

## 8. Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Backend error: ...` from a tool | Ensure `docker compose up -d` and backend health: `curl localhost:8500/health` |
| `401` from LLM in query_collection | Set a valid API key via the Settings tab or `POST /settings` |
| Tools not visible in Hermes session | Start a new session (`/reset`); tool lists load at session start |
| `hermes mcp test` shows 0 tools | Ignore; probe the server directly (see §3) or re-add with `--connect-timeout 10` |
