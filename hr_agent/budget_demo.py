"""Run the agent under deliberately tight budgets so each one fires and terminates cleanly.

Run: python -m hr_agent.budget_demo      (writes week7_output/budget_termination.log)

Uses Q09 (the transfer question), which needs several laps, so every budget is reachable.
"""
import json
import logging
import time
from pathlib import Path

from hr_agent.agent import Budget, run_agent

OUT = Path(__file__).resolve().parent.parent / "week7_output" / "budget_termination.log"
QUESTION = next(q for q in json.loads((Path(__file__).parent / "questions.json").read_text())
                if q["id"] == "Q09")["question"]

TIGHT = {
    "max_iters": Budget(max_iters=2),
    "max_tokens": Budget(max_tokens=3_000),
    "max_cost": Budget(max_cost_usd=0.0002),
    "wall_clock": Budget(max_wall_s=1.5),
}


def main():
    OUT.parent.mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(OUT, mode="w", encoding="utf-8")])
    logging.getLogger("httpx").setLevel(logging.WARNING)
    for name, budget in TIGHT.items():
        logging.info("===== demo: tight %s budget =====", name)
        result = run_agent(QUESTION, budget)
        logging.info("result status=%s answer=%s", result["status"], result["answer"])
        time.sleep(20)  # let the provider's per-minute token window refill between demos
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
