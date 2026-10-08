import os

# "dense"  -> vector search only (baseline)
# "hybrid" -> BM25 + dense fused with Reciprocal Rank Fusion (the single Week 4 improvement)
RETRIEVAL_MODE = os.environ.get("RETRIEVAL_MODE", "hybrid")

# "pinecone" or "local". Defaults to Pinecone when a key is set, else an in-memory index
# built from the local chunk store with the same embedding model.
DENSE_BACKEND = os.environ.get(
    "DENSE_BACKEND", "pinecone" if os.environ.get("PINECONE_API_KEY") else "local"
)

PINECONE_NAMESPACE = os.environ.get("PINECONE_NAMESPACE", "")

CHUNK_STORE_PATH = os.environ.get(
    "CHUNK_STORE_PATH",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "chunks.json"),
)

RRF_K = 60
