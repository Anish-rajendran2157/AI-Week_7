"""The same HR entitlement task as a fixed workflow: hard-coded steps, no loop.

Run: python -m hr_agent.workflow "How many sick days does E106 get?"

Same model (llm.MODEL), same tool functions (hr_agent.tools), same output contract
(contract.SYSTEM_PROMPT / parse_answer) as the agent. The model never chooses a tool:
  1. LLM   extract employee_id + topic from the question
  2. tool  get_employee_record(employee_id)
  3. tool  get_jurisdiction_rules(record.jurisdiction, topic)
  4. tool  search_handbook("<topic> <record.employment_type>")
  5. LLM   compose the contract JSON from the three tool results
Exactly two LLM calls and three tool calls per question, whatever the input.
"""
import json
import sys
import time

from groq import APIError

from hr_agent import llm
from hr_agent.contract import SYSTEM_PROMPT, parse_answer
from hr_agent.tools import TOPICS, get_employee_record, get_jurisdiction_rules, search_handbook

EXTRACT_PROMPT = f"""Extract the employee ID and the entitlement topic from the HR question.
Reply with only JSON: {{"employee_id": "E###", "topic": one of {json.dumps(TOPICS)}}}"""


def run_workflow(question: str) -> dict:
    start = time.perf_counter()
    used = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost_usd": 0.0, "backoff_s": 0.0}
    tool_trace = []

    def add(usage):
        for k in used:
            used[k] += usage[k]

    def finish(status, answer=None):
        wall = time.perf_counter() - start
        return {"status": status, "answer": answer, "laps": 2, "tool_calls": tool_trace,
                **used, "latency_s": wall - used["backoff_s"]}

    try:
        # Step 1: extract employee_id and topic.
        msg, usage = llm.chat(
            [{"role": "system", "content": EXTRACT_PROMPT}, {"role": "user", "content": question}],
            response_format={"type": "json_object"},
        )
        add(usage)
        try:
            parsed = json.loads(msg.content)
            employee_id, topic = str(parsed["employee_id"]), str(parsed["topic"])
        except (json.JSONDecodeError, KeyError, TypeError):
            return finish("bad_output")

        # Steps 2-4: the same three tools, in a fixed order.
        record = get_employee_record(employee_id)
        tool_trace.append(f"get_employee_record({employee_id})")
        jurisdiction = record.get("jurisdiction", "")
        rules = get_jurisdiction_rules(jurisdiction, topic)
        tool_trace.append(f"get_jurisdiction_rules({jurisdiction}, {topic})")
        query = f"{topic.replace('_', ' ')} {record.get('employment_type', '')}"
        clauses = search_handbook(query)
        tool_trace.append(f"search_handbook({query})")

        # Step 5: compose the answer under the same output contract as the agent.
        context = json.dumps({"get_employee_record": record, "get_jurisdiction_rules": rules,
                              "search_handbook": clauses}, indent=1)
        msg, usage = llm.chat(
            [{"role": "system", "content": SYSTEM_PROMPT},
             {"role": "user", "content": f"{question}\n\nTool results:\n{context}"}],
            response_format={"type": "json_object"},
        )
        add(usage)
    except APIError as e:
        print(f"LLM error: {e}", file=sys.stderr)
        return finish("error")

    answer = parse_answer(msg.content)
    return finish("ok" if answer else "bad_output", answer)


if __name__ == "__main__":
    print(json.dumps(run_workflow(" ".join(sys.argv[1:])), indent=2))
