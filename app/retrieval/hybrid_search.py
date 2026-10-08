from typing import List, Dict, Any
from app import config
from app.retrieval.vector_search import perform_vector_search
from app.retrieval.bm25_search import perform_bm25_search

def reciprocal_rank_fusion(ranked_lists: Dict[str, List[Dict[str, Any]]], k: int = config.RRF_K) -> List[Dict[str, Any]]:
    """RRF_score(d) = sum over lists of 1 / (k + rank(d)), rank starting at 1."""
    fused: Dict[str, Dict[str, Any]] = {}
    for name, results in ranked_lists.items():
        for rank, r in enumerate(results, start=1):
            cid = r["payload"]["chunk_id"]
            entry = fused.setdefault(cid, {"score": 0.0, "payload": r["payload"], "ranks": {}, "scores": {}})
            entry["score"] += 1.0 / (k + rank)
            entry["ranks"][name] = rank
            entry["scores"][name] = r["score"]
    return sorted(fused.values(), key=lambda e: -e["score"])

def perform_hybrid_search(query: str, top_k: int = 5, mode: str | None = None) -> List[Dict[str, Any]]:
    mode = mode or config.RETRIEVAL_MODE
    vector_results = perform_vector_search(query, top_k=top_k)
    if mode == "dense":
        return [{**r, "ranks": {"dense": i}, "scores": {"dense": r["score"]}}
                for i, r in enumerate(vector_results, start=1)]
    bm25_results = perform_bm25_search(query, top_k=top_k)
    return reciprocal_rank_fusion({"dense": vector_results, "bm25": bm25_results})[:top_k]
