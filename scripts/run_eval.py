"""Failure-separation evaluation: dense baseline vs hybrid (BM25 + dense, RRF).

For every gold question: retrieve top-3, generate an answer from exactly those chunks,
then classify the outcome:
  SUCCESS            gold evidence chunk in top-3 AND answer contains the key facts
  RETRIEVAL_FAILURE  gold evidence chunk NOT in top-3 ("wrong document fetched")
  GENERATION_FAILURE gold evidence chunk in top-3 but the answer is wrong/incomplete/refused
Refusal cases are generation-only: a correct refusal is SUCCESS, anything else is a
GENERATION_FAILURE (hallucination).

Without GROQ_API_KEY the generation step is skipped and only retrieval is classified.

    python -m scripts.run_eval                 # both modes + comparison
    python -m scripts.run_eval --modes dense
"""
import argparse
import json
import os
import re
import time

from dotenv import load_dotenv
load_dotenv(override=True)

from app import config
from app.eval.dataset import GOLD_QUESTIONS, REFUSAL_CASES
from app.services.retrieval_service import retrieval_service

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "eval_output")
TOP_K = 3
POOL_K = 10
REFUSAL_MARKERS = ("cannot answer", "can't answer", "not contained", "not in the provided", "no information")

HAS_LLM = bool(os.environ.get("GROQ_API_KEY"))


def is_hit(chunk: dict, q) -> bool:
    text = chunk["payload"]["text"].lower()
    return chunk["payload"].get("page_id") in q.gold_page_ids and all(e.lower() in text for e in q.evidence)


def normalize(text: str) -> str:
    # "15,000" / "15\u202f000" must match "15000"; strip thousands separators and markdown
    text = re.sub(r"(?<=\d)[,\u202f\u00a0 ](?=\d{3}\b)", "", text)
    return text.replace("*", "").replace("`", "").lower()


def answer_correct(answer: str, q) -> bool:
    return all(normalize(k) in normalize(answer) for k in q.answer_keywords) and not refused(answer)


def refused(answer: str) -> bool:
    return any(m in answer.lower() for m in REFUSAL_MARKERS)


def generate(question: str, chunks: list) -> str | None:
    if not HAS_LLM:
        return None
    from app.services.rag_service import RAGService
    for attempt in range(3):
        try:
            return RAGService().answer_from_chunks(question, chunks)["answer"]
        except Exception as e:  # rate limits etc.
            if attempt == 2:
                return f"<generation error: {e!r}>"
            time.sleep(5 * (attempt + 1))


def chunk_view(r: dict, hit: bool) -> dict:
    p = r["payload"]
    return {"chunk_id": p["chunk_id"], "page_id": p.get("page_id"), "score": round(r["score"], 4),
            "ranks": r.get("ranks", {}), "is_gold": hit, "text": p["text"]}


def evaluate(mode: str) -> dict:
    rows = []
    for q in GOLD_QUESTIONS:
        pool = retrieval_service.retrieve(q.question, initial_k=POOL_K, final_k=POOL_K, mode=mode)
        top = pool[:TOP_K]
        hits = [is_hit(r, q) for r in pool]
        hit_rank = hits.index(True) + 1 if any(hits) else None
        retrieval_hit = hit_rank is not None and hit_rank <= TOP_K

        answer = generate(q.question, top)
        if answer is None:
            answer_ok = None
            label = "RETRIEVAL_OK (generation not run)" if retrieval_hit else "RETRIEVAL_FAILURE"
        else:
            answer_ok = answer_correct(answer, q)
            if not retrieval_hit:
                label = "RETRIEVAL_FAILURE"
            else:
                label = "SUCCESS" if answer_ok else "GENERATION_FAILURE"

        rows.append({"qid": q.qid, "question": q.question, "ground_truth": q.ground_truth,
                     "gold_page_ids": list(q.gold_page_ids), "gold_rank_in_pool": hit_rank,
                     "retrieval_hit@3": retrieval_hit, "answer": answer, "answer_correct": answer_ok,
                     "classification": label,
                     "retrieved": [chunk_view(r, h) for r, h in zip(top, hits)]})

    refusals = []
    for rc in REFUSAL_CASES:
        top = retrieval_service.retrieve(rc.question, initial_k=POOL_K, final_k=TOP_K, mode=mode)
        answer = generate(rc.question, top)
        label = ("GENERATION_NOT_RUN" if answer is None
                 else "SUCCESS (refused)" if refused(answer) else "GENERATION_FAILURE (hallucinated)")
        refusals.append({"qid": rc.qid, "question": rc.question, "ground_truth": "Refuse: " + rc.why_unanswerable,
                         "answer": answer, "classification": label,
                         "retrieved": [chunk_view(r, False) for r in top]})

    return {"summary": summarize(mode, rows), "rows": rows, "refusals": refusals}


def summarize(mode: str, rows: list) -> dict:
    n = len(rows)
    hits3 = sum(r["retrieval_hit@3"] for r in rows)
    ranks = [r["gold_rank_in_pool"] for r in rows]
    return {
        "mode": mode, "dense_backend": config.DENSE_BACKEND, "n_questions": n,
        "hit_rate@3": hits3 / n, "hits@3": hits3,
        "hit_rate@1": sum(1 for x in ranks if x == 1) / n,
        "hit_rate@10": sum(1 for x in ranks if x) / n,
        "mrr@10": sum(1 / x for x in ranks if x) / n,
        "retrieval_failures": sum(r["classification"] == "RETRIEVAL_FAILURE" for r in rows),
        "generation_failures": sum(r["classification"] == "GENERATION_FAILURE" for r in rows),
        "successes": sum(r["classification"] == "SUCCESS" for r in rows),
        "generation_run": HAS_LLM,
    }


def rescore(res: dict) -> dict:
    """Re-grade saved answers (no new LLM calls) after a grader fix."""
    by_id = {q.qid: q for q in GOLD_QUESTIONS}
    for r in res["rows"]:
        if r["answer"] is None or not r["retrieval_hit@3"]:
            continue
        r["answer_correct"] = answer_correct(r["answer"], by_id[r["qid"]])
        r["classification"] = "SUCCESS" if r["answer_correct"] else "GENERATION_FAILURE"
    res["summary"] = summarize(res["summary"]["mode"], res["rows"])
    return res


def md_cell(s) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def write_inspection(result: dict, path: str):
    s = result["summary"]
    L = [f"# Inspection view — `{s['mode']}` retrieval", "",
         f"Dense backend: `{s['dense_backend']}` · generation run: `{s['generation_run']}`", "",
         f"**hit-rate@3 = {s['hits@3']}/{s['n_questions']} = {s['hit_rate@3']:.1%}** · "
         f"hit@1 {s['hit_rate@1']:.1%} · hit@10 {s['hit_rate@10']:.1%} · MRR@10 {s['mrr@10']:.3f}", "",
         "| QID | Question | Retrieved top-3 (page · score · ranks) | LLM answer | Ground truth | Classification |",
         "|---|---|---|---|---|---|"]
    for r in result["rows"] + result["refusals"]:
        chunks = "<br>".join(
            f"{'**✔ ' if c['is_gold'] else ''}{c['chunk_id']} · {c['score']} · "
            f"{','.join(f'{k}#{v}' for k, v in c['ranks'].items())}{'**' if c['is_gold'] else ''}"
            for c in r["retrieved"])
        answer = r["answer"] if r["answer"] is not None else "_(not run — no GROQ_API_KEY)_"
        L.append(f"| {r['qid']} | {md_cell(r['question'])} | {chunks} | {md_cell(answer[:300])} | "
                 f"{md_cell(r['ground_truth'])} | **{r['classification']}** |")
    L += ["", "## Retrieved chunk text (for diagnosis)", ""]
    for r in result["rows"]:
        L.append(f"### {r['qid']} — {r['question']}")
        L.append(f"Gold rank in top-{POOL_K} pool: {r['gold_rank_in_pool']} → {r['classification']}")
        for c in r["retrieved"]:
            L.append(f"- {'✔' if c['is_gold'] else '✘'} `{c['chunk_id']}` ({c['score']}): {md_cell(c['text'][:260])}…")
        L.append("")
    open(path, "w", encoding="utf-8").write("\n".join(L))


def write_comparison(before: dict, after: dict, path: str):
    b, a = before["summary"], after["summary"]
    L = ["# Before vs after — dense → hybrid (BM25 + dense, RRF k=60)", "",
         "| Metric | Dense (before) | Hybrid (after) |", "|---|---|---|"]
    for key, fmt in [("hit_rate@3", "{:.1%}"), ("hit_rate@1", "{:.1%}"), ("hit_rate@10", "{:.1%}"),
                     ("mrr@10", "{:.3f}"), ("retrieval_failures", "{}"), ("generation_failures", "{}"),
                     ("successes", "{}")]:
        L.append(f"| {key} | {fmt.format(b[key])} | {fmt.format(a[key])} |")
    L += ["", "| QID | Gold rank dense | Gold rank hybrid | Dense | Hybrid |", "|---|---|---|---|---|"]
    for rb, ra in zip(before["rows"], after["rows"]):
        L.append(f"| {rb['qid']} | {rb['gold_rank_in_pool']} | {ra['gold_rank_in_pool']} | "
                 f"{rb['classification']} | {ra['classification']} |")
    open(path, "w", encoding="utf-8").write("\n".join(L))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modes", nargs="+", default=["dense", "hybrid"])
    ap.add_argument("--rescore", action="store_true", help="re-grade saved eval_output/*.json without calling the LLM")
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)
    results = {}
    for mode in args.modes:
        if args.rescore:
            res = rescore(json.load(open(os.path.join(OUT_DIR, f"{mode}.json"), encoding="utf-8")))
        else:
            res = evaluate(mode)
        results[mode] = res
        json.dump(res, open(os.path.join(OUT_DIR, f"{mode}.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        write_inspection(res, os.path.join(OUT_DIR, f"inspection_{mode}.md"))
        s = res["summary"]
        print(f"[{mode}] hit-rate@3 {s['hits@3']}/{s['n_questions']} = {s['hit_rate@3']:.1%} | "
              f"MRR@10 {s['mrr@10']:.3f} | retrieval failures {s['retrieval_failures']} | "
              f"generation failures {s['generation_failures']}")
        for r in res["rows"]:
            print(f"   {r['qid']} rank={r['gold_rank_in_pool']} {r['classification']}")
    if "dense" in results and "hybrid" in results:
        write_comparison(results["dense"], results["hybrid"], os.path.join(OUT_DIR, "comparison.md"))
    if not HAS_LLM:
        print("\nGROQ_API_KEY not set: generation skipped; only retrieval was classified.")


if __name__ == "__main__":
    main()
