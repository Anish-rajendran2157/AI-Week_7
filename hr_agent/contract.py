"""Output contract shared by the agent and the workflow."""
import json
import re

OUTPUT_CONTRACT = """When you have the answer, reply with ONLY this JSON object and nothing else:
{"employee_id": "<id>", "jurisdiction": "<jurisdiction whose rule you applied>", "rule_id": "<id of the rule you applied, e.g. IN-NP-2 or HB-3>", "value": <number>, "unit": "days", "answer": "<one sentence for the employee>"}"""

SYSTEM_PROMPT = f"""You are an HR entitlement assistant for Northwind. Each question is about one employee.
Work from facts only: the employee's record (tenure, jurisdiction, employment type, FTE, transfer) and the
handbook rules. Every number in your answer must come from a tool result or arithmetic on tool results.

{OUTPUT_CONTRACT}"""

FIELDS = ("employee_id", "jurisdiction", "rule_id", "value", "unit", "answer")


def parse_answer(text: str):
    """Extract the contract JSON from model text. Returns None if it does not conform."""
    if not text:
        return None
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        obj = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not all(k in obj for k in FIELDS):
        return None
    try:
        obj["value"] = float(obj["value"])
    except (TypeError, ValueError):
        return None
    return obj
