import re
from typing import List, Dict, Any

from rank_bm25 import BM25Okapi

from app.retrieval.chunk_store import chunk_store

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "of", "to", "in", "on", "for", "and", "or",
    "what", "which", "how", "do", "does", "i", "my", "me", "it", "by", "with", "when",
    "can", "be", "this", "that", "at", "as", "from", "there", "much", "many",
}


def tokenize(text: str) -> List[str]:
    # Keep snake_case identifiers (retry_backoff_ms, max_retries) as single tokens —
    # exact identifier matching is the whole point of adding BM25 for developer docs.
    return [t for t in re.findall(r"[a-z0-9_]+", text.lower()) if t not in STOPWORDS]


_index_cache: Dict[str, Any] = {"n": None, "bm25": None}


def _get_index():
    chunks = chunk_store.chunks
    # Rebuild whenever the chunk store changes size (new ingestion / deletion)
    if _index_cache["bm25"] is None or _index_cache["n"] != len(chunks):
        _index_cache["bm25"] = BM25Okapi([tokenize(c["text"]) for c in chunks]) if chunks else None
        _index_cache["n"] = len(chunks)
    return _index_cache["bm25"], chunks


def perform_bm25_search(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    bm25, chunks = _get_index()
    if bm25 is None:
        return []
    scores = bm25.get_scores(tokenize(query))
    order = sorted(range(len(chunks)), key=lambda i: -scores[i])[:top_k]
    return [{"score": float(scores[i]), "payload": chunks[i]} for i in order if scores[i] > 0]
