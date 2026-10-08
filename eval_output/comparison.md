# Before vs after — dense → hybrid (BM25 + dense, RRF k=60)

| Metric | Dense (before) | Hybrid (after) |
|---|---|---|
| hit_rate@3 | 93.8% | 93.8% |
| hit_rate@1 | 68.8% | 75.0% |
| hit_rate@10 | 100.0% | 100.0% |
| mrr@10 | 0.812 | 0.859 |
| retrieval_failures | 1 | 1 |
| generation_failures | 1 | 0 |
| successes | 14 | 15 |

| QID | Gold rank dense | Gold rank hybrid | Dense | Hybrid |
|---|---|---|---|---|
| Q01 | 1 | 1 | GENERATION_FAILURE | SUCCESS |
| Q02 | 6 | 4 | RETRIEVAL_FAILURE | RETRIEVAL_FAILURE |
| Q03 | 2 | 2 | SUCCESS | SUCCESS |
| Q04 | 2 | 2 | SUCCESS | SUCCESS |
| Q05 | 1 | 1 | SUCCESS | SUCCESS |
| Q06 | 1 | 1 | SUCCESS | SUCCESS |
| Q07 | 2 | 2 | SUCCESS | SUCCESS |
| Q08 | 1 | 1 | SUCCESS | SUCCESS |
| Q09 | 1 | 1 | SUCCESS | SUCCESS |
| Q10 | 1 | 1 | SUCCESS | SUCCESS |
| Q11 | 1 | 1 | SUCCESS | SUCCESS |
| Q12 | 1 | 1 | SUCCESS | SUCCESS |
| Q13 | 3 | 1 | SUCCESS | SUCCESS |
| Q14 | 1 | 1 | SUCCESS | SUCCESS |
| Q15 | 1 | 1 | SUCCESS | SUCCESS |
| Q16 | 1 | 1 | SUCCESS | SUCCESS |