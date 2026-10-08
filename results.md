# Week 4 — Debugging Retrieval: Failure Separation + One Improvement

**Topic:** E — Developer documentation (Acme SDK v2 + v3, 11 pages, 40 chunks of 400 chars / 80 overlap, stored in Pinecone namespace `week4-eval`)
**Test set:** 16 gold questions + 3 must-refuse questions ([app/eval/dataset.py](app/eval/dataset.py)), written from the pages before any search was run.
**LLM:** Groq `openai/gpt-oss-20b`, given exactly the top-3 retrieved chunks.
**Metric:** hit-rate@3. A hit means a top-3 chunk comes from a gold page **and** contains every evidence string, so the chunk actually holds the answer.
**Single change:** Hybrid search, where BM25 and dense (`all-MiniLM-L6-v2` on Pinecone) results are fused with Reciprocal Rank Fusion (k=60). The reranker is a pass-through, and chunking was fixed before the baseline was measured.

Reproduce: `python -m scripts.ingest_corpus` then `python -m scripts.run_eval`. Full inspection views: [eval_output/inspection_dense.md](eval_output/inspection_dense.md), [eval_output/inspection_hybrid.md](eval_output/inspection_hybrid.md).

## Before vs after

| Metric | Dense (before) | Hybrid (after) |
|---|---|---|
| **hit-rate@3** | **15/16 = 93.8%** | **15/16 = 93.8%** |
| hit-rate@1 | 68.8% | 75.0% |
| MRR@10 | 0.812 | 0.859 |
| Retrieval failures (wrong document fetched) | 1 (Q02) | 1 (Q02) |
| Generation failures (right document, wrong answer) | 1 (Q01) | 0 |
| End-to-end correct | 14/16 | 15/16 |
| Refusal cases correctly refused | 3/3 | 3/3 |

## The wrong answers

### Q01: fixed by hybrid
*"What are the type and default value of retry_backoff_ms on Client.send()?"* Ground truth: `int`, default **500**.

| | Top-3 chunks | LLM answer | Classification |
|---|---|---|---|
| **Before (dense)** | ✔ `v3-client_chunk_3`, ✘ `v2-client_chunk_2`, ✘ `v2-client_chunk_3` | "Type: `int`, Default value: `2000`" | GENERATION_FAILURE |
| **After (hybrid)** | ✔ `v3-client_chunk_3`, ✔ `v3-client_chunk_5`, ✘ `v2-client_chunk_2` | "Type: `int`, Default value: `500` (milliseconds)" | SUCCESS |

**Diagnosis:** The gold chunk was retrieved in both runs, so this counts as a generation failure. But the cause was in retrieval: 2 of the 3 dense chunks came from the **v2** client page, where `Client.request()` has `retry_backoff_ms` defaulting to 2000. The LLM went with the majority of its context. BM25 matched the exact tokens `Client.send` / `retry_backoff_ms` and pulled in `v3-client_chunk_5` (the actual `Client.send()` table), which pushed one v2 chunk out. So a "right document, wrong answer" failure can still come from noisy retrieval.

### Q02: NOT fixed
*"Which exception does the SDK raise on HTTP 429 and what attribute carries the wait time?"* Ground truth: `RateLimitError`, attribute **`retry_after_seconds`**.

| | Top-3 chunks | LLM answer | Classification |
|---|---|---|---|
| **Before (dense)** | ✘ `v2-errors_chunk_1`, ✘ `v3-errors_chunk_1`, ✘ `v3-ratelimits_chunk_1` (gold rank 6) | "…raises **`RateLimitError`** … the exception's **`retry_after`** attribute contains the wait-time" | RETRIEVAL_FAILURE |
| **After (hybrid)** | ✘ `v3-errors_chunk_1`, ✘ `v2-errors_chunk_1`, ✘ `v3-ratelimits_chunk_1` (gold rank 4) | "…raises a **`RateLimitError`** … contains a `retry_after` attribute" | RETRIEVAL_FAILURE |

**Diagnosis:** The attribute name `retry_after` is **hallucinated**. The model filled in a plausible guess because the real name was never in its context. The chunker cut `v3-errors_chunk_1` off at "The exception carries a", and `retry_after_seconds` starts the next chunk. Hybrid moved the complete chunk from rank 6 to rank 4, which still misses the top-3. No re-ranking can put the exception and the attribute into one chunk when the chunker has split them. The next change should be structure-aware chunking (split on `##` headings). This is also the case a stronger LLM can't fix, because the answer isn't in the context.

## Grader note
The first grading run marked hybrid Q09 ("**15,000 ms**") and Q13 ("**10,000 ms**") as generation failures because the keyword check required `15000` / `10000`. The answers were correct, so the grader was wrong. I fixed it to ignore thousands separators and re-graded the saved answers without calling the LLM again (`python -m scripts.run_eval --rescore`). Retrieval numbers are unaffected. Generation results come from a single LLM run and may vary slightly between runs.
