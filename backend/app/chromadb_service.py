"""Multi-collection ChromaDB service.

Supports multiple named collections.  The active collection name is
persisted in the config file so it survives container restarts.
A "Default" collection is auto-created on first init.
"""

import os
import hashlib

import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
from sentence_transformers import SentenceTransformer

from app import settings as app_settings

CHROMA_PATH = os.environ.get("CHROMA_PATH", "/app/data/chroma")
MODEL_NAME = "all-MiniLM-L6-v2"
DEFAULT_COLLECTION = "Default"


class SentenceTransformerEmbeddingFunction(EmbeddingFunction[str]):
    def __init__(self):
        self._model = SentenceTransformer(MODEL_NAME)
        print(f"[ChromaDB] Loaded embedding model: {MODEL_NAME}")

    def __call__(self, input: Documents) -> Embeddings:
        embeddings = self._model.encode(
            input,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embeddings.tolist()


class ChromaDBService:
    def __init__(self):
        self._client = chromadb.PersistentClient(path=CHROMA_PATH)
        self._emb_fn = SentenceTransformerEmbeddingFunction()
        self._collection_cache: dict[str, chromadb.Collection] = {}

        # Ensure "Default" collection exists
        self._get_or_create(DEFAULT_COLLECTION)

        # Set active collection from settings, or fall back to Default
        cfg = app_settings.get_config()
        active = cfg.get("active_collection", DEFAULT_COLLECTION)
        try:
            self._get_or_create(active)
        except Exception:
            active = DEFAULT_COLLECTION
        if cfg.get("active_collection") != active:
            app_settings.update_config(active_collection=active)
        self._active_name = active

        print(
            f"[ChromaDB] Active collection: '{self._active_name}' | "
            f"collections: {self._list_names()}"
        )

    # ── Internal helpers ────────────────────────────────────────

    def _get_or_create(self, name: str) -> chromadb.Collection:
        """Return a cached reference to the named collection."""
        if name in self._collection_cache:
            return self._collection_cache[name]
        coll = self._client.get_or_create_collection(
            name=name,
            embedding_function=self._emb_fn,
            metadata={"hnsw:space": "cosine"},
        )
        self._collection_cache[name] = coll
        return coll

    def _active_collection(self) -> chromadb.Collection:
        return self._get_or_create(self._active_name)

    def _list_names(self) -> list[str]:
        """Return all ChromaDB collection names."""
        return sorted(c.name for c in self._client.list_collections())

    # ── Public API ──────────────────────────────────────────────

    @property
    def active_collection_name(self) -> str:
        return self._active_name

    @staticmethod
    def make_doc_id(filename: str, chunk_idx: int) -> str:
        h = hashlib.sha256(f"{filename}:{chunk_idx}".encode()).hexdigest()[:16]
        return f"{h}"

    def list_collections(self) -> list[dict]:
        """Return all collections with name and doc count."""
        return [
            {
                "name": c.name,
                "doc_count": c.count(),
            }
            for c in self._client.list_collections()
        ]

    def create_collection(self, name: str) -> dict:
        """Create a new empty collection. Returns its info."""
        existing = [c.name for c in self._client.list_collections()]
        if name in existing:
            raise ValueError(f"Collection '{name}' already exists.")
        coll = self._client.create_collection(
            name=name,
            embedding_function=self._emb_fn,
            metadata={"hnsw:space": "cosine"},
        )
        self._collection_cache[name] = coll
        return {"name": name, "doc_count": 0}

    def set_active(self, name: str) -> str:
        """Switch the active collection. Persists the choice."""
        # Verify the collection exists
        available = self._list_names()
        if name not in available:
            raise ValueError(f"Collection '{name}' not found. Available: {available}")
        self._active_name = name
        app_settings.update_config(active_collection=name)
        return name

    def delete_by_filename(self, filename: str) -> int:
        """Delete all chunks with the given filename from the active collection.
        Returns the number of remaining docs, or -1 if nothing was deleted."""
        coll = self._active_collection()
        # Get all IDs for this filename
        results = coll.get(where={"filename": filename})
        ids = results.get("ids", [])
        if not ids:
            return -1
        coll.delete(ids=ids)
        return coll.count()

    def add_chunks(self, filename: str, chunks: list[str], chunk_indices: list[int]) -> int:
        """Add text chunks to the *active* collection."""
        coll = self._active_collection()
        doc_ids = [self.make_doc_id(filename, i) for i in chunk_indices]
        metadatas = [
            {"filename": filename, "chunk_index": idx, "collection": self._active_name}
            for idx in chunk_indices
        ]
        coll.add(documents=chunks, ids=doc_ids, metadatas=metadatas)
        return coll.count()

    def query(self, question: str, n_results: int = 5) -> list[dict]:
        """Query the *active* collection."""
        coll = self._active_collection()
        results = coll.query(
            query_texts=[question],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )
        items = []
        for i in range(len(results["documents"][0])):
            items.append({
                "content": results["documents"][0][i],
                "filename": results["metadatas"][0][i]["filename"],
                "chunk_index": results["metadatas"][0][i]["chunk_index"],
                "distance": results["distances"][0][i],
            })
        return items

    def count(self) -> int:
        """Doc count in the *active* collection."""
        return self._active_collection().count()

    def count_all(self) -> dict[str, int]:
        """Doc counts for every collection."""
        return {c.name: c.count() for c in self._client.list_collections()}
