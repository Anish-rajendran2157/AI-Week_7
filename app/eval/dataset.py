"""Topic E (developer docs, Acme SDK v2/v3) evaluation set.

Written from the corpus pages BEFORE running any search. A retrieval "hit" means one of the
top-3 chunks comes from a gold page AND contains every string in `evidence` — i.e. the chunk
actually holds the answer, not just a chunk from the right file.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class GoldQuestion:
    qid: str
    question: str
    gold_page_ids: tuple[str, ...]
    evidence: tuple[str, ...]         # must all appear in one retrieved gold chunk
    answer_keywords: tuple[str, ...]  # must all appear in the LLM answer
    ground_truth: str


GOLD_QUESTIONS = (
    GoldQuestion("Q01", "What are the type and default value of retry_backoff_ms on Client.send()?",
                 ("v3-client",), ("retry_backoff_ms", "500"), ("int", "500"),
                 "int, default 500 (ms)."),
    GoldQuestion("Q02", "Which exception does the SDK raise on HTTP 429 and what attribute carries the wait time?",
                 ("v3-errors",), ("RateLimitError", "retry_after_seconds"), ("RateLimitError", "retry_after_seconds"),
                 "RateLimitError; retry_after_seconds."),
    GoldQuestion("Q03", "What is the maximum file size accepted by uploads in v3?",
                 ("v3-files",), ("max_file_size_mb", "25"), ("25",),
                 "25 MB (max_file_size_mb=25)."),
    GoldQuestion("Q04", "How do I verify a webhook signature in v3?",
                 ("v3-webhooks",), ("verify_signature", "X-Acme-Signature"), ("verify_signature", "X-Acme-Signature"),
                 "Call acme.webhooks.verify_signature() with the raw body, the X-Acme-Signature header and the signing secret."),
    GoldQuestion("Q05", "What is the default buffer_size_ms for streaming?",
                 ("v3-streaming",), ("buffer_size_ms", "250"), ("250",),
                 "250 ms."),
    GoldQuestion("Q06", "How many requests per minute does the free tier allow?",
                 ("v3-ratelimits",), ("Free", "60"), ("60",),
                 "60 requests per minute (burst 10)."),
    GoldQuestion("Q07", "How do I disable automatic retries when creating the client?",
                 ("v3-client", "v3-errors"), ("max_retries=0",), ("max_retries=0",),
                 "Pass max_retries=0 to the Client constructor."),
    GoldQuestion("Q08", "Which environment variable holds the API token?",
                 ("v3-client",), ("ACME_API_TOKEN",), ("ACME_API_TOKEN",),
                 "ACME_API_TOKEN."),
    GoldQuestion("Q09", "What is the default heartbeat_interval_ms on a stream?",
                 ("v3-streaming",), ("heartbeat_interval_ms", "15000"), ("15000",),
                 "15000 ms."),
    GoldQuestion("Q10", "What is the default tolerance_seconds when verifying webhooks and why does it exist?",
                 ("v3-webhooks",), ("tolerance_seconds", "300"), ("300", "replay"),
                 "300 seconds; stale deliveries are rejected to protect against replay attacks."),
    GoldQuestion("Q11", "Which header lets a dropped stream replay events it missed?",
                 ("v3-streaming",), ("Last-Event-ID",), ("Last-Event-ID",),
                 "Last-Event-ID."),
    GoldQuestion("Q12", "What should I use instead of paginate_auto() in v3?",
                 ("v3-changelog", "v2-pagination"), ("paginate_auto", "list_after"), ("list_after",),
                 "Explicit cursor pagination via list_after()."),
    GoldQuestion("Q13", "What is the default request timeout in v3 and which option sets it?",
                 ("v3-client", "v3-changelog"), ("timeout_ms", "10000"), ("timeout_ms", "10000"),
                 "timeout_ms, default 10000 ms (10 s)."),
    GoldQuestion("Q14", "How long can an interrupted multipart upload be resumed, and with what value?",
                 ("v3-files",), ("24 hours", "upload_id"), ("24", "upload_id"),
                 "Within 24 hours, by passing the returned upload_id back to Client.files.upload()."),
    GoldQuestion("Q15", "Which response header tells me how many requests I have left?",
                 ("v3-ratelimits",), ("X-RateLimit-Remaining",), ("X-RateLimit-Remaining",),
                 "X-RateLimit-Remaining."),
    GoldQuestion("Q16", "How many consecutive failed deliveries before a webhook endpoint is disabled?",
                 ("v3-webhooks",), ("20 consecutive failures",), ("20",),
                 "20 consecutive failures."),
)


@dataclass(frozen=True)
class RefusalCase:
    qid: str
    question: str
    why_unanswerable: str


REFUSAL_CASES = (
    RefusalCase("R01", "How do I rotate my account password with the SDK?",
                "Password management is documented nowhere in the corpus."),
    RefusalCase("R02", "Does the SDK publish events to Kafka for stream processing?",
                "Kafka integration appears nowhere in the corpus."),
    RefusalCase("R03", "How do I install the SDK with pip?",
                "Installation instructions are not part of any indexed page."),
)
