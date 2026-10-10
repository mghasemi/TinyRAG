"""FastAPI application — Tiny RAG backend."""

import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import engine, SessionLocal
from app.models import Base, Document, QueryLog
from app.chromadb_service import ChromaDBService, DEFAULT_COLLECTION
from app.ingest import extract_text, chunk_text, UPLOAD_DIR
from app import llm as llm_module
from app import settings as app_settings

# ── Init ──────────────────────────────────────────────────────────────────────

Base.metadata.create_all(bind=engine)

# Migrate existing DBs — add collection column if missing
with engine.connect() as conn:
    for table, col in [("documents", "collection"), ("query_logs", "collection"), ("documents", "chroma_doc_id")]:
        try:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} VARCHAR(256) DEFAULT NULL"))
            conn.commit()
            print(f"[Migrate] Added '{col}' to {table}")
        except Exception:
            conn.rollback()  # column already exists

chroma = ChromaDBService()

app = FastAPI(title="Tiny RAG", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── POST /ingest ─────────────────────────────────────────────────────────────

@app.post("/ingest")
async def ingest(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a .txt, .md, or .pdf document. Extracts text, chunks it, stores
    embeddings in ChromaDB (active collection), and logs metadata in SQLite."""

    # Validate extension
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("txt", "md", "pdf"):
        raise HTTPException(400, f"Unsupported file type: .{ext}. Allowed: .txt, .md, .pdf")

    # Save to disk
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}_{file.filename}"
    filepath = os.path.join(UPLOAD_DIR, safe_name)

    content = await file.read()
    file_size = len(content)
    with open(filepath, "wb") as f:
        f.write(content)

    try:
        # Extract & chunk
        text_content = extract_text(filepath, ext)
        if not text_content.strip():
            raise HTTPException(400, "Extracted text is empty — document may be unreadable.")

        chunks = chunk_text(text_content)
        chunk_indices = list(range(len(chunks)))

        # Store in ChromaDB (active collection)
        chroma.add_chunks(safe_name, chunks, chunk_indices)

        # Log in SQLite with collection name
        doc = Document(
            filename=file.filename,
            file_type=ext,
            file_size=file_size,
            upload_timestamp=datetime.utcnow(),
            chunk_count=len(chunks),
            collection=chroma.active_collection_name,
            chroma_doc_id=safe_name,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        return {
            "status": "ok",
            "document_id": doc.id,
            "filename": file.filename,
            "file_type": ext,
            "file_size": file_size,
            "chunk_count": len(chunks),
            "collection": chroma.active_collection_name,
        }
    finally:
        # Clean up uploaded file after processing
        if os.path.exists(filepath):
            os.remove(filepath)


# ── GET /documents ───────────────────────────────────────────────────────────

@app.get("/documents")
async def list_documents(db: Session = Depends(get_db)):
    """Return documents from the active collection."""
    active = chroma.active_collection_name
    docs = (
        db.query(Document)
        .filter(Document.collection == active)
        .order_by(Document.upload_timestamp.desc())
        .all()
    )
    return [
        {
            "id": d.id,
            "filename": d.filename,
            "file_type": d.file_type,
            "file_size": d.file_size,
            "upload_timestamp": d.upload_timestamp.isoformat(),
            "chunk_count": d.chunk_count,
            "collection": d.collection,
        }
        for d in docs
    ]


# ── DELETE /documents/{id} ────────────────────────────────────────────────────


@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: int, db: Session = Depends(get_db)):
    """Delete a document from SQLite and its chunks from ChromaDB."""
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, f"Document {doc_id} not found.")

    # Delete from ChromaDB using safe_name
    if doc.chroma_doc_id:
        chroma.delete_by_filename(doc.chroma_doc_id)

    # Delete from SQLite
    db.delete(doc)
    db.commit()

    return {"status": "ok", "deleted_id": doc_id, "filename": doc.filename}


# ── POST /qa ─────────────────────────────────────────────────────────────────

async def qa_stream(question: str) -> AsyncGenerator[str, None]:
    """Generator that yields JSON lines for the QA endpoint.
    Each line is a JSON string — no SSE framing (handled by caller).
    """
    start = time.monotonic()

    # Retrieve relevant chunks from active collection
    chunks = chroma.query(question, n_results=5)
    if not chunks:
        yield __import__('json').dumps({'token': 'No relevant documents found in the knowledge base.'})
        yield "[DONE]"
        return

    # Deduplicate source filenames for reporting
    source_filenames = list(dict.fromkeys(c["filename"] for c in chunks))

    # Stream LLM response
    async for line in llm_module.stream_response(question, chunks):
        yield line

    # Log query
    elapsed_ms = (time.monotonic() - start) * 1000
    query_log = QueryLog(
        query=question,
        timestamp=datetime.utcnow(),
        source_count=len(chunks),
        latency_ms=round(elapsed_ms, 1),
        collection=chroma.active_collection_name,
    )
    try:
        db = SessionLocal()
        db.add(query_log)
        db.commit()
        db.close()
    except Exception:
        pass  # Don't block streaming on logging failure

    # Append source info as final message
    yield __import__('json').dumps({'sources': source_filenames})
    yield "[DONE]"


@app.post("/qa")
async def qa(question: dict):
    """Accept a question, retrieve context, stream LLM answer with source refs."""
    q = question.get("question", "").strip()
    if not q:
        raise HTTPException(400, "Question is required.")

    from fastapi.responses import StreamingResponse
    sse_gen = (f"data: {line}\n\n" async for line in qa_stream(q))
    return StreamingResponse(sse_gen, media_type="text/event-stream")


# ── GET/POST /settings ───────────────────────────────────────────────────────


@app.get("/settings")
async def get_settings():
    """Return current config (API key masked for display)."""
    cfg = app_settings.get_config()
    return {
        "base_url": cfg["base_url"],
        "model": cfg["model"],
        "api_key": cfg["api_key"][:8] + "..." if cfg["api_key"] else "",
        "active_collection": chroma.active_collection_name,
    }


@app.post("/settings")
async def update_settings(body: dict):
    """Update config (model, base_url, api_key)."""
    updates = {}
    for key in ("model", "base_url", "api_key"):
        if key in body:
            updates[key] = body[key]
    app_settings.update_config(**updates)
    cfg = app_settings.get_config()
    return {
        "status": "ok",
        "base_url": cfg["base_url"],
        "model": cfg["model"],
        "api_key": cfg["api_key"][:8] + "..." if cfg["api_key"] else "",
        "active_collection": chroma.active_collection_name,
    }


# ── Collections ──────────────────────────────────────────────────────────────


@app.get("/collections")
async def list_collections():
    """Return all ChromaDB collections with doc counts."""
    return {"collections": chroma.list_collections(), "active": chroma.active_collection_name}


@app.post("/collections")
async def create_collection(body: dict):
    """Create a new collection."""
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(400, "Collection name is required.")
    if not name.replace(" ", "").isalnum():
        raise HTTPException(400, "Collection name must be alphanumeric (spaces allowed).")
    try:
        info = chroma.create_collection(name)
        return {"status": "ok", "collection": info}
    except ValueError as e:
        raise HTTPException(409, str(e))


@app.get("/collections/active")
async def get_active_collection():
    """Return the active collection name."""
    return {"name": chroma.active_collection_name, "doc_count": chroma.count()}


@app.post("/collections/active")
async def set_active_collection(body: dict):
    """Switch the active collection."""
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(400, "Collection name is required.")
    try:
        chroma.set_active(name)
        return {"status": "ok", "name": name, "doc_count": chroma.count()}
    except ValueError as e:
        raise HTTPException(404, str(e))


# ── GET /health ──────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "active_collection": chroma.active_collection_name,
        "collections": chroma.list_collections(),
    }
