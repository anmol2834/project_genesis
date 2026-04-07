"""
emailservice — Kafka Client (compatibility shim → Redis Streams)
=================================================================
All workers import from kafka_client. This shim delegates every call
to stream_client.py which uses the existing Upstash Redis connection.

No aiokafka, no separate Kafka broker, no new credentials needed.
The REDIS_URL in .env is the only connection string required.

Public API (unchanged from original kafka_client.py):
  publish(topic, payload, partition_key)
  publish_batch(topic, events)
  make_consumer(topics, group_id) → StreamConsumer
  ensure_topics()
  close_producer()                → no-op (Redis connections managed by pool)
"""
from __future__ import annotations

# Re-export everything from stream_client under the original names
from stream_client import (
    publish,
    publish_batch,
    StreamConsumer as _StreamConsumer,
    ensure_streams as _ensure_streams,
)
import logging

logger = logging.getLogger("emailservice.kafka")


def make_consumer(topics: list[str], group_id: str, auto_commit: bool = False):
    """
    Returns a StreamConsumer (Redis Streams) with the same interface
    as the old AIOKafkaConsumer used by BaseWorker.
    """
    return _StreamConsumer(streams=topics, group_id=group_id)


async def ensure_topics() -> None:
    """Ensure all Redis Streams and consumer groups exist."""
    await _ensure_streams()


async def close_producer() -> None:
    """No-op — Redis connections are managed by the shared pool."""
    pass
