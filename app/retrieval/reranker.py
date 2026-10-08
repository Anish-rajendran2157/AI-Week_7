from typing import List, Dict, Any

def rerank_results(query: str, results: List[Dict[str, Any]], top_k: int = 3) -> List[Dict[str, Any]]:
    # Intentionally a pass-through: Week 4 allows exactly ONE retrieval change, and that
    # change is hybrid BM25 + RRF. A cross-encoder here would confound the before/after number.
    return results[:top_k]
