"""
emailservice — Metrics & Observability
Prometheus counters/histograms exposed on :9090/metrics.
Falls back to no-op if prometheus_client is not installed.

Usage:
    from metrics import M
    M.messages_processed.labels(provider="gmail", status="ok").inc()
    with M.processing_latency.labels(stage="fetch").time():
        ...
"""
from __future__ import annotations
import time, logging
from typing import Any

logger = logging.getLogger("emailservice.metrics")

# ── Try to import prometheus_client ──────────────────────────────────────────
try:
    from prometheus_client import (
        Counter, Histogram, Gauge, start_http_server, REGISTRY
    )
    _PROM_AVAILABLE = True
except ImportError:
    _PROM_AVAILABLE = False
    logger.warning("prometheus_client not installed — metrics disabled")


# ── No-op stubs when prometheus unavailable ───────────────────────────────────
class _NoOpMetric:
    def labels(self, **_): return self
    def inc(self, *_, **__): pass
    def dec(self, *_, **__): pass
    def set(self, *_, **__): pass
    def observe(self, *_, **__): pass
    def time(self): return _NoOpCtx()

class _NoOpCtx:
    def __enter__(self): return self
    def __exit__(self, *_): pass


def _counter(name, doc, labels=()):
    if _PROM_AVAILABLE:
        return Counter(name, doc, list(labels))
    return _NoOpMetric()

def _histogram(name, doc, labels=(), buckets=None):
    if _PROM_AVAILABLE:
        kw = {"buckets": buckets} if buckets else {}
        return Histogram(name, doc, list(labels), **kw)
    return _NoOpMetric()

def _gauge(name, doc, labels=()):
    if _PROM_AVAILABLE:
        return Gauge(name, doc, list(labels))
    return _NoOpMetric()


# ═════════════════════════════════════════════════════════════════════════════
# METRIC DEFINITIONS
# ═════════════════════════════════════════════════════════════════════════════

class _Metrics:
    # ── Throughput ────────────────────────────────────────────────────────────
    messages_processed = _counter(
        "es_messages_processed_total",
        "Total messages processed",
        ["provider", "status"],
    )
    messages_filtered = _counter(
        "es_messages_filtered_total",
        "Messages rejected by filter",
        ["reason"],
    )
    messages_deduped = _counter(
        "es_messages_deduped_total",
        "Messages skipped by dedup",
        ["layer"],   # bloom | db | idempotency
    )
    dlq_events = _counter(
        "es_dlq_events_total",
        "Events sent to Dead Letter Queue",
        ["reason"],
    )

    # ── Latency ───────────────────────────────────────────────────────────────
    processing_latency = _histogram(
        "es_processing_latency_seconds",
        "End-to-end processing latency per stage",
        ["stage"],   # fetch | filter | storage | ai_handoff
        buckets=[.005, .01, .025, .05, .1, .25, .5, 1.0, 2.5, 5.0],
    )
    api_call_latency = _histogram(
        "es_api_call_latency_seconds",
        "External API call latency",
        ["provider", "endpoint"],
        buckets=[.05, .1, .25, .5, 1.0, 2.5, 5.0, 10.0],
    )

    # ── API cost ──────────────────────────────────────────────────────────────
    api_calls = _counter(
        "es_api_calls_total",
        "Total external API calls made",
        ["provider", "endpoint"],
    )
    api_errors = _counter(
        "es_api_errors_total",
        "External API errors",
        ["provider", "status_code"],
    )
    api_rate_limited = _counter(
        "es_api_rate_limited_total",
        "API rate limit hits",
        ["provider"],
    )

    # ── Queue health ──────────────────────────────────────────────────────────
    kafka_lag = _gauge(
        "es_kafka_consumer_lag",
        "Kafka consumer lag per topic",
        ["topic", "worker"],
    )
    buffer_size = _gauge(
        "es_user_buffer_size",
        "Current user aggregation buffer size",
        ["worker"],
    )
    active_users = _gauge(
        "es_active_users_in_buffer",
        "Users currently in aggregation buffer",
        ["worker"],
    )

    # ── Priority distribution ─────────────────────────────────────────────────
    priority_events = _counter(
        "es_priority_events_total",
        "Events processed by priority level",
        ["priority"],   # critical | high | medium | low
    )

    # ── Hot users ─────────────────────────────────────────────────────────────
    hot_users_detected = _counter(
        "es_hot_users_detected_total",
        "Users detected as high-volume",
        [],
    )

    # ── DB writes ─────────────────────────────────────────────────────────────
    db_writes = _counter(
        "es_db_writes_total",
        "Database write operations",
        ["table", "status"],
    )
    db_write_batch_size = _histogram(
        "es_db_write_batch_size",
        "Rows per bulk INSERT",
        ["table"],
        buckets=[1, 5, 10, 25, 50, 100, 200],
    )


M = _Metrics()


def start_metrics_server(port: int = 9090) -> None:
    """Start Prometheus HTTP server on given port."""
    if not _PROM_AVAILABLE:
        return
    try:
        start_http_server(port)
        logger.info("Prometheus metrics server started on :%d", port)
    except Exception as e:
        logger.warning("Failed to start metrics server: %s", e)


# ── Timing context manager ────────────────────────────────────────────────────
class timer:
    """
    Usage:
        async with timer("fetch", provider="gmail"):
            ...
    Records to M.processing_latency.
    """
    def __init__(self, stage: str, **_):
        self.stage = stage
        self._t0   = 0.0

    async def __aenter__(self):
        self._t0 = time.monotonic()
        return self

    async def __aexit__(self, *_):
        elapsed = time.monotonic() - self._t0
        M.processing_latency.labels(stage=self.stage).observe(elapsed)
