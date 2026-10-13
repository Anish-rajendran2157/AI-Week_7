# Week 7 — Task Set C: race the HR agent against a fixed workflow

Domain: HR policy (fictional Northwind handbook, 10 employees, 4 jurisdictions).
Model for both systems: `openai/gpt-oss-20b` on Groq, `temperature=0`, `reasoning_effort=low`.

## Run it

```bash
pip install -r requirements.txt          # needs GROQ_API_KEY in .env
python -m hr_agent.agent "How many paid sick days does E106 get?"     # agent (tool-calling loop)
python -m hr_agent.workflow "How many paid sick days does E106 get?"  # fixed workflow (no loop)
python -m hr_agent.race                  # race over the 10 questions -> week7_output/race.csv
python -m hr_agent.budget_demo           # tight budgets -> week7_output/budget_termination.log
```

| File | What it is |
|---|---|
| [hr_agent/agent.py](hr_agent/agent.py) | Agent loop with all four budgets enforced before every lap |
| [hr_agent/workflow.py](hr_agent/workflow.py) | Fixed workflow: same tools, model and output contract; 2 LLM calls + 3 tool calls, no loop |
| [hr_agent/tools.py](hr_agent/tools.py) | `get_employee_record`, `search_handbook`, new `get_jurisdiction_rules` |
| [hr_agent/contract.py](hr_agent/contract.py) | Shared system prompt + output contract (`employee_id, jurisdiction, rule_id, value, unit, answer`) |
| [hr_agent/questions.json](hr_agent/questions.json) | The 10 race questions with expected values and the reasoning for each |
| [week7_output/race.csv](week7_output/race.csv) | The 8 numbers |
| [week7_output/race_runs.csv](week7_output/race_runs.csv) | Per-question rows: value, rule, laps, tokens, latency, tool trace |
| [week7_output/budget_termination.log](week7_output/budget_termination.log) | One clean termination per budget |
| [week7_output/tool_description.diff](week7_output/tool_description.diff) | Third tool + sharpened descriptions and enums |

## 1. Race results (same 10 questions, one run each)

| system | pass rate | p50 latency (s) | total tokens (10 q, every call summed) | cost / question (USD) |
|---|---|---|---|---|
| agent | **100%** (10/10) | 2.16 | 24,870 | $0.000226 |
| workflow | 90% (9/10) | **1.13** | **10,373** | **$0.000107** |

Tokens are the sum of `prompt + completion` over *every* LLM call (the agent re-sends the whole
message list each lap, 3–4 laps per question). Cost uses $0.075 / 1M input and $0.30 / 1M output
(Groq gpt-oss-20b, third-party price trackers, Oct 2026; override with `PRICE_IN_PER_M` / `PRICE_OUT_PER_M`).
Latency excludes time slept on Groq HTTP 429 rate limits (recorded separately as `backoff_s`).

Per question:

| Q | class | agent | workflow | expected | workflow got |
|---|---|---|---|---|---|
| Q01 | single-lookup | PASS | PASS | 5 | 5 |
| Q02 | tenure-branch (18 mo → IN-NP-2) | PASS | PASS | 30 | 30 |
| Q03 | tenure-branch (6 yrs × 7, UK-NP-2) | PASS | PASS | 42 | 42 |
| Q04 | tenure-branch + carry-over | PASS | PASS | 17 | 17 |
| Q05 | tenure-branch (< 24 mo) | PASS | PASS | 10 | 10 |
| Q06 | tenure-branch (probation, 0 days) | PASS | PASS | 0 | 0 |
| Q07 | tenure-branch (< 12 mo) | PASS | PASS | 10 | 10 |
| Q08 | part-time (28 × 0.6 → 16.5) | PASS | PASS | 16.5 | 16.5 |
| Q09 | **transfer IN → UK** | PASS | **FAIL** | 28 | 0 ("UK jurisdiction rules are not provided") |
| Q10 | contractor (HB-3) | PASS | PASS | 0 | 0 |

Seven questions have step 3 depending on what step 2 found (Q02–Q08: the tenure band or FTE in the
record selects the rule). The workflow handles all of them, because the dependency is in the *data*
the final step reads, not in *which tools* are called. Q09 is different: the jurisdiction whose
rules must be fetched is not the record's `jurisdiction` field, it is the transfer destination, and
that is only known after reading the record and the HB-2 transfer clause. The workflow's fixed step 3
fetched `get_jurisdiction_rules(IN, notice_period)`; its final LLM call correctly read HB-2, realised
UK rules were needed, and had no way to fetch them. The agent called `get_jurisdiction_rules(UK, …)`.

## 2. Workflow is the same task

Same question in, same contract JSON out, same three tool functions, same model and settings.
Steps are hard-coded: (1) LLM extracts `employee_id` + `topic` → (2) `get_employee_record` →
(3) `get_jurisdiction_rules(record.jurisdiction, topic)` → (4) `search_handbook("<topic> <employment_type>")`
→ (5) LLM composes the contract JSON. No loop, no model-chosen tool calls; every question costs
exactly 2 LLM calls and 3 tool calls.

## 3. Budgets — all four enforced in the loop

`Budget(max_iters=6, max_tokens=20_000, max_cost_usd=0.003, max_wall_s=90)`, checked in
`_budget_fired` before every lap. Token and cost checks are *projected* (`used + last lap > cap`),
since each lap re-sends the full history and costs at least as much as the previous one; the loop
stops before the lap that would cross the cap. Wall-clock is also enforced inside the call: the
request timeout is the time left, and a rate-limit sleep past the deadline aborts.

Excerpt from [budget_termination.log](week7_output/budget_termination.log) (Q09, tight max_tokens = 3000):

```
INFO START question='E108 is relocating to the UK office on 1 November 2026. ...' budget={'max_iters': 6, 'max_tokens': 3000, 'max_cost_usd': 0.003, 'max_wall_s': 90.0}
INFO lap 1: +572 tokens (prompt 541) -> total 572 tokens, $0.000050, 0.2s elapsed
INFO lap 1: tool get_employee_record({"employee_id":"E108"})
INFO lap 2: +717 tokens (prompt 683) -> total 1289 tokens, $0.000111, 0.8s elapsed
INFO lap 2: tool search_handbook({"query":"notice period"})
INFO lap 3: +923 tokens (prompt 884) -> total 2212 tokens, $0.000189, 1.4s elapsed
INFO lap 3: tool get_jurisdiction_rules({"jurisdiction":"UK","topic":"notice_period"})
WARNING BUDGET FIRED: max_tokens (used 2212 + next lap >= 923 > limit 3000) -> terminating cleanly before lap 4
INFO END status=budget:max_tokens laps=3 tokens=2212 cost=$0.000189 latency=1.37s
```

The same log has the other three firing: `max_iters` (limit 2), `max_cost` ($0.0002) and
`wall_clock` (1.5 s; the lap-4 request timed out and the run ended with `status=budget:wall_clock`).

## 4. Third tool — `get_jurisdiction_rules`

One job: return the entitlement rule table for one jurisdiction and one topic.
`jurisdiction` is `enum ["IN","UK","US-CA","SG"]`, `topic` is `enum ["annual_leave","notice_period","sick_leave"]`,
`additionalProperties: false`. To remove overlap, the numeric tables moved out of the handbook text
into `jurisdiction_rules.json`, and both old descriptions were sharpened (they previously both
claimed "leave entitlements" and "employee information"):

```diff
-  get_employee_record: "Get information about an employee, including their leave entitlements and the HR policies that apply to them."
+  get_employee_record: "Look up one employee's personal HR record by employee ID: jurisdiction, employment type, FTE, tenure in
+                        completed months, annual leave taken, carry-over days and any approved transfer. Facts about the person
+                        only; contains no policy rules or entitlement amounts."   (employee_id: pattern ^E[0-9]{3}$)
-  search_handbook:     "Search the HR handbook for policies, leave entitlements and employee information."
+  search_handbook:     "Keyword search over the handbook's general policy clauses (HB-1 to HB-6: tenure, transfers, contractors,
+                        carry-over, probation, part-time) and return the matching clause text. Contains no per-jurisdiction
+                        entitlement amounts."
+  get_jurisdiction_rules: "Return the entitlement rule table for one jurisdiction and one topic: rule IDs with tenure bands and
+                           the number of days for each band."   (jurisdiction: enum, topic: enum)
```

Full code diff: [tool_description.diff](week7_output/tool_description.diff).

## 5. Verdict

Decision rule: does the path vary by input? For 9 of 10 questions, no. Tenure bands, part-time
pro-rating and contractor status change the data the final step reads, not which tools run, and
the workflow passed all nine at about half the agent's p50 latency (1.13 s vs 2.16 s), 42% of the
tokens and 47% of the cost per question. The one class that forces a different path is the
**cross-jurisdiction transfer** (Q09): which jurisdiction's rules to fetch is only known after
reading the record and the transfer clause, so the fixed step fetched IN rules and failed. The
agent passed it. Ship the workflow by default; send transfer questions to the agent, or add one
explicit transfer branch, which turns that class back into a fixed path.

*(Verdict: 129 words.)*

### Caveats

- One run per question per system (n = 10), `temperature=0`. Q09 was re-run outside the race for
  both systems and gave the same outcome (agent 28 via UK-NP-2; workflow "UK rules not provided").
  This is not a variance study.
- Prices come from third-party trackers, not Groq's own page; the ratio between the systems does
  not depend on the price.
- The baseline two-tool agent (commit `Week 7: hand-built HR entitlement agent`) was rebuilt in this
  repo, since the Week 6 code had no agent; the tool diff is measured against it.
- Bonus (sliding window + summarisation, persisted jurisdiction) was not attempted.
