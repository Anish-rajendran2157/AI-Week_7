"""Hand-built HR entitlement agent: a tool-calling loop over the HR tools.

Run: python -m hr_agent.agent "How many sick days does E106 get?"
"""
import json
import sys

from hr_agent import llm
from hr_agent.contract import SYSTEM_PROMPT, parse_answer
from hr_agent.tools import TOOL_SCHEMAS, call_tool

MAX_ITERS = 8


def _assistant_message(msg) -> dict:
    out = {"role": "assistant", "content": msg.content or ""}
    if msg.tool_calls:
        out["tool_calls"] = [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in msg.tool_calls
        ]
    return out


def run_agent(question: str) -> dict:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": question}]
    tokens = 0
    for i in range(MAX_ITERS):
        msg, usage = llm.chat(messages, tools=TOOL_SCHEMAS)
        tokens += usage["total_tokens"]
        messages.append(_assistant_message(msg))
        if not msg.tool_calls:
            return {"status": "ok", "answer": parse_answer(msg.content), "iterations": i + 1, "tokens": tokens}
        for tc in msg.tool_calls:
            result = call_tool(tc.function.name, tc.function.arguments)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)})
    return {"status": "max_iters", "answer": None, "iterations": MAX_ITERS, "tokens": tokens}


if __name__ == "__main__":
    print(json.dumps(run_agent(" ".join(sys.argv[1:])), indent=2))
