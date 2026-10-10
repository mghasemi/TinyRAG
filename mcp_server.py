#!/usr/bin/env python3
"""MCP server for TinyRAG — exposes collections and RAG query tools.

Run standalone (stdio MCP transport):
    python mcp_server.py

Register with Hermes:
    hermes mcp add tinyrag --command "python /path/to/mcp_server.py"

Then load the "tinyrag-search" skill so the agent knows how to use
the tools it exposes.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass

import httpx
from mcp.types import (
    TextContent,
    Tool,
    ServerCapabilities,
)
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

# ── Config ──────────────────────────────────────────────────────────────────

BACKEND_URL = os.environ.get("TINYRAG_URL", "http://localhost:8500")
server = Server("tinyrag")


# ── API helpers ─────────────────────────────────────────────────────────────


@dataclass
class ApiClient:
    """Thin HTTP client for the TinyRAG REST API."""

    base: str

    def _url(self, path: str) -> str:
        return f"{self.base}{path}"

    def list_collections(self) -> list[dict]:
        r = httpx.get(self._url("/collections"), timeout=10)
        r.raise_for_status()
        data = r.json()
        return data.get("collections", [])

    def search_chunks(self, question: str, collection: str | None = None,
                      n_results: int = 5) -> str:
        """Retrieve raw chunks without LLM generation. Returns raw SSE text."""
        if collection:
            httpx.post(
                self._url("/collections/active"),
                json={"name": collection},
                timeout=10,
            ).raise_for_status()

        r = httpx.post(
            self._url("/qa"),
            json={"question": question},
            timeout=60,
        )
        r.raise_for_status()
        return r.text  # raw SSE — caller parses it

    def query_rag(self, question: str, collection: str | None = None,
                  n_results: int = 5) -> dict:
        """Send a question and get back the full_response + sources."""
        if collection:
            httpx.post(
                self._url("/collections/active"),
                json={"name": collection},
                timeout=10,
            ).raise_for_status()

        r = httpx.post(
            self._url("/qa"),
            json={"question": question},
            timeout=120,
        )
        r.raise_for_status()

        # Parse SSE stream
        full_response = ""
        sources: list[str] = []
        for line in r.iter_lines():
            if not line.startswith("data: "):
                continue
            body = line[6:]
            if not body.startswith("{"):
                continue
            try:
                data = json.loads(body)
                if "token" in data:
                    full_response += data["token"]
                elif "full_response" in data:
                    full_response = data["full_response"]
                elif "sources" in data:
                    sources = data["sources"]
                elif "error" in data:
                    return {"error": data["error"], "sources": []}
            except json.JSONDecodeError:
                continue

        return {"response": full_response.strip(), "sources": sources}


_client = ApiClient(BACKEND_URL)


# ── Tool listing ────────────────────────────────────────────────────────────


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_collections",
            description="List all TinyRAG collections with document counts.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="query_collection",
            description=(
                "Ask a question against a TinyRAG collection. "
                "Returns an answer generated from the collection's documents, "
                "plus the source filenames. If collection is omitted, uses the "
                "currently active collection."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question to answer",
                    },
                    "collection": {
                        "type": "string",
                        "description": "Collection name (optional — uses active if omitted)",
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "Number of context chunks to retrieve (default 5)",
                        "default": 5,
                    },
                },
                "required": ["question"],
            },
        ),
        Tool(
            name="search_chunks",
            description=(
                "Search a TinyRAG collection and return raw context chunks "
                "matching the query, without LLM generation. Useful for "
                "inspecting what documents are relevant."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "collection": {
                        "type": "string",
                        "description": "Collection name (optional)",
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "Number of chunks (default 5)",
                        "default": 5,
                    },
                },
                "required": ["question"],
            },
        ),
    ]


# ── Tool call handler ───────────────────────────────────────────────────────


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "list_collections":
            collections = _client.list_collections()
            lines = [
                f"  • {c['name']} — {c['doc_count']} document(s)"
                for c in collections
            ]
            return [TextContent(
                type="text",
                text="Collections:\n" + "\n".join(lines) if lines else "No collections found."
            )]

        elif name == "query_collection":
            question = arguments.get("question", "").strip()
            if not question:
                return [TextContent(type="text", text="Error: question is required.")]

            collection = arguments.get("collection")
            n_results = arguments.get("n_results", 5)

            result = _client.query_rag(question, collection, n_results)
            if "error" in result:
                return [TextContent(type="text", text=f"Error: {result['error']}")]

            response = result.get("response", "")
            sources = result.get("sources", [])

            text = response
            if sources:
                text += "\n\n--- Sources ---\n" + "\n".join(
                    f"  • {s.split('_', 1)[1] if '_' in s else s}"
                    for s in sources
                )

            return [TextContent(type="text", text=text)]

        elif name == "search_chunks":
            question = arguments.get("question", "").strip()
            if not question:
                return [TextContent(type="text", text="Error: question is required.")]

            collection = arguments.get("collection")
            n_results = arguments.get("n_results", 5)

            raw = _client.search_chunks(question, collection, n_results)

            # Parse the SSE and extract just the context tokens
            tokens = []
            for line in raw.splitlines():
                if not line.startswith("data: "):
                    continue
                body = line[6:]
                if not body.startswith("{"):
                    continue
                try:
                    data = json.loads(body)
                    if "token" in data:
                        tokens.append(data["token"])
                except json.JSONDecodeError:
                    continue

            text = "Context chunks:\n\n" + "".join(tokens).strip() if tokens else "No results found."
            return [TextContent(type="text", text=text)]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except httpx.HTTPError as e:
        return [TextContent(type="text", text=f"Backend error: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {type(e).__name__}: {e}")]


# ── Entry point ─────────────────────────────────────────────────────────────


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="tinyrag",
                server_version="1.0.0",
                capabilities=ServerCapabilities(),
            ),
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
