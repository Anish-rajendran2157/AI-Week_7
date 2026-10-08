"""Chunk data/corpus/**/*.md, write data/chunks.json (BM25 + local dense index) and,
if PINECONE_API_KEY is set, upsert the same chunks into Pinecone.

    python -m scripts.ingest_corpus
"""
import glob
import os
import re

from dotenv import load_dotenv
load_dotenv(override=True)

from app import config
from app.embeddings.model import embedding_model
from app.ingestion.chunker import recursive_chunk
from app.ingestion.cleaner import clean_text
from app.ingestion.metadata import create_metadata
from app.retrieval.chunk_store import chunk_store

CORPUS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "corpus")
# Fixed before the baseline was measured; NOT part of the Week 4 change.
CHUNK_SIZE = 400
CHUNK_OVERLAP = 80


def main():
    all_meta = []
    for path in sorted(glob.glob(os.path.join(CORPUS_DIR, "**", "*.md"), recursive=True)):
        raw = open(path, encoding="utf-8").read()
        page_id = re.search(r"^page_id:\s*(\S+)", raw, re.M).group(1)
        title = raw.splitlines()[0].lstrip("# ").strip()
        chunks = recursive_chunk(clean_text(raw), chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
        meta = create_metadata(page_id, os.path.relpath(path, CORPUS_DIR).replace("\\", "/"), "file", title, chunks)
        for m in meta:
            m["page_id"] = page_id
        all_meta.extend(meta)
        print(f"{page_id:15s} {len(chunks)} chunks")

    chunk_store.replace_all(all_meta)
    print(f"Wrote {len(all_meta)} chunks to {chunk_store.path}")

    if os.environ.get("PINECONE_API_KEY"):
        from app.vectorstore.pinecone_store import pinecone_store
        embeddings = embedding_model.encode([m["text"] for m in all_meta])
        pinecone_store.upsert_chunks(all_meta, embeddings, namespace=config.PINECONE_NAMESPACE)
        print(f"Upserted {len(all_meta)} vectors to Pinecone namespace '{config.PINECONE_NAMESPACE}'")
    else:
        print("PINECONE_API_KEY not set - skipping Pinecone; dense search will use the local index.")


if __name__ == "__main__":
    main()
