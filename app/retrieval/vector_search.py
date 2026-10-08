from app import config
from app.embeddings.model import embedding_model
from app.retrieval.chunk_store import chunk_store
from typing import List, Dict, Any

def perform_vector_search(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    query_emb = embedding_model.encode([query])[0]
    if config.DENSE_BACKEND == "pinecone":
        from app.vectorstore.pinecone_store import pinecone_store
        return pinecone_store.search(query_emb, limit=top_k, namespace=config.PINECONE_NAMESPACE)
    return chunk_store.dense_search(query_emb, limit=top_k)
