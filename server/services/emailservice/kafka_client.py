"""
emailservice — Kafka Client (compatibility shim → Redis Streams)
=================================================================
Delegates to stream_client.py (event-driven, zero idle cost).
No XREADGROUP. No consumer groups. No blocking reads.
"""
from __future__ import annotations
from stream_client import (
    publish,
    publish_batch,
    ensure_streams as _ensure_streams,
)
import logging

logger = logging.getLogger("emailservice.kafka")


def make_consumer(topics: list[str], group_id: str, auto_commit: bool = False):
    """
    Returns an EventDrivenConsumer wrapped in the StreamConsumer shim.
    BaseWorker uses this — it calls .start() and .drain_once() internally.
    """
    from stream_client import EventDrivenConsumer
    return EventDrivenConsumer(topics)


async def ensure_topics() -> None:
    await _ensure_streams()


async def close_producer() -> None:
    pass  # Redis connections managed by shared pool
