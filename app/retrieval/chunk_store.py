import json
import os
from typing import List, Dict, Any

import numpy as np

from app import config
from app.embeddings.model import embedding_model


class ChunkStore:
    """Local copy of every indexed chunk's metadata + text.

    BM25 needs the full chunk corpus, which Pinecone cannot enumerate cheaply, so
    ingestion writes each chunk here as well. It also backs the "local" dense backend.
    """

    def __init__(self, path: str = config.CHUNK_STORE_PATH):
        self.path = path
        self._chunks: List[Dict[str, Any]] | None = None
        self._embeddings: np.ndarray | None = None

    @property
    def chunks(self) -> List[Dict[str, Any]]:
        if self._chunks is None:
            if os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8") as f:
                    self._chunks = json.load(f)
            else:
                self._chunks = []
        return self._chunks

    def _save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.chunks, f, indent=2, ensure_ascii=False)
        self._embeddings = None

    def add(self, chunks_metadata: List[Dict[str, Any]]):
        new_ids = {c["chunk_id"] for c in chunks_metadata}
        self._chunks = [c for c in self.chunks if c["chunk_id"] not in new_ids] + list(chunks_metadata)
        self._save()

    def replace_all(self, chunks_metadata: List[Dict[str, Any]]):
        self._chunks = list(chunks_metadata)
        self._save()

    def delete_document(self, document_id: str):
        self._chunks = [c for c in self.chunks if c["document_id"] != document_id]
        self._save()

    def dense_search(self, query_embedding: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        if not self.chunks:
            return []
        if self._embeddings is None:
            emb = np.array(embedding_model.encode([c["text"] for c in self.chunks]))
            self._embeddings = emb / np.linalg.norm(emb, axis=1, keepdims=True)
        q = np.array(query_embedding)
        scores = self._embeddings @ (q / np.linalg.norm(q))
        order = np.argsort(-scores)[:limit]
        return [{"score": float(scores[i]), "payload": self.chunks[i]} for i in order]


chunk_store = ChunkStore()
