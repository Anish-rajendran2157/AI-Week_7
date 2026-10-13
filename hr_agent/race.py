"""Race the agent against the fixed workflow over the same 10 employee questions.

Run: python -m hr_agent.race            (writes week7_output/race.csv and race_runs.csv)

Per system: pass rate, p50 latency, total tokens (every call summed), cost per question.
A question passes when the contract JSON's value matches the expected value.
Latency excludes time slept on provider rate limits (HTTP 429), which is reported separately.
"""
import argparse
import csv
import json
import statistics
import time
from pathlib import Path

from hr_agent.agent import run_agent
from hr_agent.workflow import run_workflow

QUESTIONS = json.loads((Path(__file__).parent / "questions.json").read_text())
OUT_DIR = Path(__file__).resolve().parent.parent / "week7_output"
SYSTEMS = {"agent": run_agent, "workflow": run_workflow}


def passed(result, q) -> bool:
    answer = result["answer"]
    return bool(answer) and abs(answer["value"] - q["expected_value"]) < 0.01


def summarise(rows, system):
    runs = [r for r in rows if r["system"] == system]
    return {
        "system": system,
        "pass_rate": sum(r["pass"] for r in runs) / len(runs),
        "p50_latency_s": statistics.median(r["latency_s"] for r in runs),
        "total_tokens": sum(r["total_tokens"] for r in runs),
        "cost_per_question_usd": sum(r["cost_usd"] for r in runs) / len(runs),
        "runs": len(runs),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--only", nargs="*", help="question ids to run, e.g. Q01 Q09")
    p.add_argument("--pause", type=float, default=0.0, help="seconds to wait between runs (rate limits)")
    args = p.parse_args()

    questions = [q for q in QUESTIONS if not args.only or q["id"] in args.only]
    rows = []
    for q in questions:
        for system, fn in SYSTEMS.items():
            r = fn(q["question"])
            a = r["answer"] or {}
            row = {
                "question_id": q["id"], "class": q["class"], "system": system, "status": r["status"],
                "pass": passed(r, q), "expected_value": q["expected_value"], "value": a.get("value"),
                "expected_rule": q["expected_rule"], "rule_id": a.get("rule_id"),
                "laps": r["laps"], "tool_calls": len(r["tool_calls"]),
                "prompt_tokens": r["prompt_tokens"], "completion_tokens": r["completion_tokens"],
                "total_tokens": r["total_tokens"], "cost_usd": round(r["cost_usd"], 8),
                "latency_s": round(r["latency_s"], 3), "backoff_s": round(r["backoff_s"], 1),
                "trace": " | ".join(r["tool_calls"]),
            }
            rows.append(row)
            print(f"{q['id']} {system:8s} {'PASS' if row['pass'] else 'FAIL'} value={row['value']} "
                  f"(want {q['expected_value']}) rule={row['rule_id']} tokens={row['total_tokens']} "
                  f"{row['latency_s']}s status={row['status']}")
            time.sleep(args.pause)

    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / "race_runs.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    summary = [summarise(rows, s) for s in SYSTEMS]
    with open(OUT_DIR / "race.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0]))
        w.writeheader()
        w.writerows(summary)

    print("\n| system | pass rate | p50 latency (s) | total tokens | cost / question (USD) |")
    print("|---|---|---|---|---|")
    for s in summary:
        print(f"| {s['system']} | {s['pass_rate']:.0%} | {s['p50_latency_s']:.2f} | {s['total_tokens']} "
              f"| ${s['cost_per_question_usd']:.6f} |")
    print(f"\nWrote {OUT_DIR / 'race.csv'} and {OUT_DIR / 'race_runs.csv'}")


if __name__ == "__main__":
    main()
