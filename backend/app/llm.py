"""Streaming LLM completion via OpenAI-compatible API.

Settings (base_url, api_key, model) are resolved at *call time* from
the persistent settings module so the frontend can reconfigure the
provider without a container restart.
"""

import json

import httpx

from app import settings as app_settings


def build_prompt(question: str, context_chunks: list[dict]) -> str:
    """Build a RAG prompt from question + retrieved context."""
    sources_text = ""
    for i, chunk in enumerate(context_chunks, 1):
        sources_text += (
            f"[Source {i}: {chunk['filename']} (chunk {chunk['chunk_index']})]\n"
            f"{chunk['content']}\n\n"
        )

    return (
        "You are a helpful AI assistant. Answer the user's question based "
        "ONLY on the provided context documents below. If the context does not "
        "contain enough information, say so clearly.\n\n"
        "=== Context Documents ===\n"
        f"{sources_text}"
        "=== End of Context ===\n\n"
        f"Question: {question}\n\n"
        "Answer:"
    )


async def stream_response(question: str, context_chunks: list[dict]):
    """Stream LLM response tokens as JSON lines.

    Each yielded value is a JSON string:
      {"token": "..."}  or  {"done": true, "full_response": "..."}
    """
    cfg = app_settings.get_config()

    prompt = build_prompt(question, context_chunks)

    headers = {
        "Content-Type": "application/json",
    }
    if cfg["api_key"]:
        headers["Authorization"] = f"Bearer {cfg['api_key']}"

    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": "You are a helpful RAG assistant. Answer based on the provided context."},
            {"role": "user", "content": prompt},
        ],
        "stream": True,
        "temperature": 0.3,
        "max_tokens": 2048,
    }

    full_response = []

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{cfg['base_url']}/chat/completions",
            json=payload,
            headers=headers,
        ) as resp:
            if resp.status_code != 200:
                error_text = await resp.aread()
                yield json.dumps({
                    "error": f"LLM API returned {resp.status_code}: {error_text.decode()}"
                })
                return

            async for line in resp.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]  # strip "data: "
                if data_str.strip() == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                    choices = data.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    token = delta.get("content", "")
                    if token:
                        full_response.append(token)
                        yield json.dumps({"token": token})
                except json.JSONDecodeError:
                    continue

    # Final signal with full response
    yield json.dumps({
        "done": True,
        "full_response": "".join(full_response),
    })
