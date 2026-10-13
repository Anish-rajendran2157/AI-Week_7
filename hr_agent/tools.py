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


TOOL_FUNCTIONS = {
    "get_employee_record": get_employee_record,
    "search_handbook": search_handbook,
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_employee_record",
            "description": "Get information about an employee, including their leave entitlements "
                           "and the HR policies that apply to them.",
            "parameters": {
                "type": "object",
                "properties": {"employee_id": {"type": "string", "description": "Employee ID"}},
                "required": ["employee_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_handbook",
            "description": "Search the HR handbook for policies, leave entitlements and employee information.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "What to search for"}},
                "required": ["query"],
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
