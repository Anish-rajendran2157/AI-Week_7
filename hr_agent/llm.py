"""Groq chat wrapper that meters every call: tokens, cost and latency.

Every lap of the agent and every step of the workflow goes through `chat`, so per-call usage
is summed by the caller. The loop re-sends the whole message list each lap, so the prompt
tokens of *every* call count, not only the final one.
"""
import os
import time

from dotenv import load_dotenv

load_dotenv(override=True)

from groq import Groq, RateLimitError  # noqa: E402

MODEL = os.environ.get("HR_AGENT_MODEL", "openai/gpt-oss-20b")
# USD per 1M tokens for openai/gpt-oss-20b on Groq (third-party trackers, checked 2026-10).
PRICE_IN_PER_M = float(os.environ.get("PRICE_IN_PER_M", "0.075"))
PRICE_OUT_PER_M = float(os.environ.get("PRICE_OUT_PER_M", "0.30"))

MAX_RATE_LIMIT_RETRIES = 6

_client = None


def get_client() -> Groq:
    global _client
    if _client is None:
        # SDK retries are disabled so rate-limit waits are visible and excluded from latency.
        _client = Groq(max_retries=0)
    return _client


def cost_usd(prompt_tokens: int, completion_tokens: int) -> float:
    return (prompt_tokens * PRICE_IN_PER_M + completion_tokens * PRICE_OUT_PER_M) / 1_000_000


def chat(messages, tools=None, timeout=None, **kwargs):
    """Returns (message, usage) where usage has tokens, cost, latency_s and backoff_s.

    latency_s is time spent in successful requests; backoff_s is time slept on HTTP 429.
    """
    params = dict(model=MODEL, messages=messages, temperature=0, reasoning_effort="low", **kwargs)
    if tools:
        params["tools"] = tools
        params["tool_choice"] = "auto"
    if timeout is not None:
        params["timeout"] = timeout

    backoff_s = 0.0
    for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
        start = time.perf_counter()
        try:
            resp = get_client().chat.completions.create(**params)
            latency_s = time.perf_counter() - start
            break
        except RateLimitError as e:
            if attempt == MAX_RATE_LIMIT_RETRIES:
                raise
            wait = float(e.response.headers.get("retry-after", 2 ** attempt))
            time.sleep(wait)
            backoff_s += wait

    u = resp.usage
    usage = {
        "prompt_tokens": u.prompt_tokens,
        "completion_tokens": u.completion_tokens,
        "total_tokens": u.prompt_tokens + u.completion_tokens,
        "cost_usd": cost_usd(u.prompt_tokens, u.completion_tokens),
        "latency_s": latency_s,
        "backoff_s": backoff_s,
    }
    return resp.choices[0].message, usage
