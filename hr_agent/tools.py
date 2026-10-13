"""HR agent tools: plain Python functions plus their JSON schemas for tool calling."""
import json
import re
from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
AS_OF = date(2026, 10, 1)

_EMPLOYEES = {e["employee_id"]: e for e in json.loads((DATA_DIR / "employees.json").read_text())}


def _tenure_months(hire_date: str) -> int:
    hired = date.fromisoformat(hire_date)
    months = (AS_OF.year - hired.year) * 12 + (AS_OF.month - hired.month)
    if AS_OF.day < hired.day:
        months -= 1
    return months


def get_employee_record(employee_id: str) -> dict:
    record = _EMPLOYEES.get(employee_id.strip().upper())
    if record is None:
        return {"error": f"no employee with id {employee_id!r}"}
    return {**record, "as_of": AS_OF.isoformat(), "tenure_months": _tenure_months(record["hire_date"])}


def _sections(text: str):
    for block in re.split(r"^## ", text, flags=re.MULTILINE)[1:]:
        heading, _, body = block.partition("\n")
        yield heading.strip(), body.strip()


def _tokens(text: str) -> set:
    return set(re.findall(r"[a-z0-9][a-z0-9-]*", text.lower()))


_HANDBOOK = list(_sections((DATA_DIR / "handbook.md").read_text()))


def search_handbook(query: str, top_k: int = 3) -> list:
    q = _tokens(query)
    scored = []
    for heading, body in _HANDBOOK:
        score = 2 * len(q & _tokens(heading)) + len(q & _tokens(body))
        if score:
            scored.append((score, heading, body))
    scored.sort(key=lambda s: -s[0])
    return [{"section": h, "text": b} for _, h, b in scored[:top_k]]


JURISDICTIONS = ["IN", "UK", "US-CA", "SG"]
TOPICS = ["annual_leave", "notice_period", "sick_leave"]

_RULES = json.loads((DATA_DIR / "jurisdiction_rules.json").read_text())


def get_jurisdiction_rules(jurisdiction: str, topic: str) -> dict:
    if jurisdiction not in JURISDICTIONS:
        return {"error": f"jurisdiction must be one of {JURISDICTIONS}"}
    if topic not in TOPICS:
        return {"error": f"topic must be one of {TOPICS}"}
    return {
        "jurisdiction": jurisdiction,
        "topic": topic,
        "bands": "tenure in completed months; min_months inclusive, max_months exclusive, null = no upper bound",
        "rules": _RULES[jurisdiction][topic],
    }


TOOL_FUNCTIONS = {
    "get_employee_record": get_employee_record,
    "search_handbook": search_handbook,
    "get_jurisdiction_rules": get_jurisdiction_rules,
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_employee_record",
            "description": "Look up one employee's personal HR record by employee ID: jurisdiction, "
                           "employment type, FTE, tenure in completed months, annual leave taken, "
                           "carry-over days and any approved transfer. Facts about the person only; "
                           "contains no policy rules or entitlement amounts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "employee_id": {"type": "string", "pattern": "^E[0-9]{3}$",
                                    "description": "Employee ID, e.g. E104"},
                },
                "required": ["employee_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_handbook",
            "description": "Keyword search over the handbook's general policy clauses (HB-1 to HB-6: "
                           "tenure, transfers, contractors, carry-over, probation, part-time) and return "
                           "the matching clause text. Contains no per-jurisdiction entitlement amounts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Keywords, e.g. 'part-time annual leave'"},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_jurisdiction_rules",
            "description": "Return the entitlement rule table for one jurisdiction and one topic: "
                           "rule IDs with tenure bands and the number of days for each band.",
            "parameters": {
                "type": "object",
                "properties": {
                    "jurisdiction": {"type": "string", "enum": JURISDICTIONS},
                    "topic": {"type": "string", "enum": TOPICS},
                },
                "required": ["jurisdiction", "topic"],
                "additionalProperties": False,
            },
        },
    },
]


def call_tool(name: str, arguments: str):
    """Dispatch a model tool call. Bad names/arguments come back as an error the model can read."""
    fn = TOOL_FUNCTIONS.get(name)
    if fn is None:
        return {"error": f"unknown tool {name!r}"}
    try:
        args = json.loads(arguments or "{}")
        return fn(**args)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        return {"error": f"bad arguments for {name}: {e}"}
