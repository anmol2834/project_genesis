"""
Messaging Layer
================
Namespace facade over app/workers/ — the actual implementations live there.

Architecture:
--------------
  emailservice → automation_events (Redis Stream)
    → StreamConsumer (BLPOP notify + XRANGE drain)
    → WorkerRuntime (priority sort, retry queue, DLQ)
    → MessageProcessor (validation + DB enrichment)
    → WorkerExecutionEngine → orchestration pipeline
    → automation_responses (Redis Stream) → emailservice

Delivery guarantee:
  At-least-once with dedup protection.
  Messages are XDEL'd from the stream only AFTER the full AI pipeline
  reaches a terminal state (response sent or DLQ'd).
  A 10-minute dedup key (automation:processed:{message_id}) prevents
  double-sending within the restart window.

Scaling:
  Run ONE process per container.  Scale horizontally by deploying multiple
  containers — each owns its BLPOP connection and processes independent
  batches.  The dedup key handles the rare cross-container race.

Worker concurrency within a process:
  Controlled by the AUTOMATION_WORKER_CONCURRENCY env var (default: 1).

Dead Letter Queue:
  Messages that exceed AUTOMATION_MAX_RETRIES are pushed to
  automation_dlq stream for manual inspection / replay.
"""

# Re-export the primary consumer so callers can import from messaging.*
from app.workers.consumer import StreamConsumer, STREAM_AUTOMATION_EVENTS, POLL_INTERVAL_S
from app.workers.runtime  import WorkerRuntime, get_worker_runtime

__all__ = [
    "StreamConsumer",
    "WorkerRuntime",
    "get_worker_runtime",
    "STREAM_AUTOMATION_EVENTS",
    "POLL_INTERVAL_S",
]
