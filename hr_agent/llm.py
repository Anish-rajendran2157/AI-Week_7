"""Groq chat wrapper that meters every call: tokens, cost and latency.

Every lap of the agent and every step of the workflow goes through `chat`, so per-call usage
is summed by the caller. The loop re-sends the whole message list each lap, so the prompt
tokens of *every* call count, not only the final one.
"""
import os
import time

from dotenv import load_dotenv

load_dotenv(override=True)

from groq import APITimeoutError, Groq, RateLimitError  # noqa: E402

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


class DeadlineExceeded(Exception):
    """The call could not finish before the caller's wall-clock deadline."""


def chat(messages, tools=None, deadline=None, **kwargs):
    """Returns (message, usage) where usage has tokens, cost, latency_s and backoff_s.

    latency_s is time spent in successful requests; backoff_s is time slept on HTTP 429.
    deadline is a time.perf_counter() value: the request timeout is the time left until it,
    and a rate-limit sleep that would cross it raises DeadlineExceeded instead of sleeping.
    """
    params = dict(model=MODEL, messages=messages, temperature=0, reasoning_effort="low", **kwargs)
    if tools:
        params["tools"] = tools
        params["tool_choice"] = "auto"

    backoff_s = 0.0
    for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
        if deadline is not None:
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                raise DeadlineExceeded("no wall-clock time left for the call")
            params["timeout"] = remaining
        start = time.perf_counter()
        try:
            resp = get_client().chat.completions.create(**params)
            latency_s = time.perf_counter() - start
            break
        except APITimeoutError as e:
            raise DeadlineExceeded(f"request timed out after {time.perf_counter() - start:.1f}s") from e
        except RateLimitError as e:
            if attempt == MAX_RATE_LIMIT_RETRIES:
                raise
            wait = float(e.response.headers.get("retry-after", 2 ** attempt))
            if deadline is not None and time.perf_counter() + wait > deadline:
                raise DeadlineExceeded(f"rate-limited; retry-after {wait:.0f}s is past the deadline") from e
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
