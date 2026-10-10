"""Text extraction and chunking utilities."""

import os
import fitz  # PyMuPDF


UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/app/uploads")

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def extract_text(filepath: str, file_type: str) -> str:
    """Extract plain text from .txt, .md, or .pdf files."""
    if file_type in ("txt", "md"):
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    if file_type == "pdf":
        doc = fitz.open(filepath)
        pages_text = []
        for page in doc:
            pages_text.append(page.get_text())
        doc.close()
        return "\n\n".join(pages_text)

    raise ValueError(f"Unsupported file type: {file_type}")


def chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks of CHUNK_SIZE characters."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk = text[start:end]
        # Try to break at a sentence or line boundary instead of mid-sentence
        if end < len(text):
            # Look backwards for a good break point
            for break_char in [". ", "\n\n", "\n", "  "]:
                last_break = chunk.rfind(break_char)
                if last_break > CHUNK_OVERLAP:
                    chunk = chunk[: last_break + len(break_char)]
                    end = start + len(chunk)
                    break
        chunks.append(chunk.strip())
        start = end - CHUNK_OVERLAP
    return [c for c in chunks if c]
