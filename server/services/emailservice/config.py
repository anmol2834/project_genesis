"""
emailservice — Unified Configuration (v2 — optimized for 1M users)
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from shared.config import get_config as _shared_cfg

def get_config():
    return _shared_cfg()

# ═════════════════════════════════════════════════════════════════════════════
# KAFKA TOPICS
# ═════════════════════════════════════════════════════════════════════════════
TOPIC_GMAIL_RAW     = "gmail_events"
TOPIC_OUTLOOK_RAW   = "outlook_events"
TOPIC_SMTP_RAW      = "smtp_events"
TOPIC_FETCH_RESULTS = "fetch_results"
TOPIC_STORE_READY   = "store_ready"
TOPIC_AI_EVENTS     = "ai_events"
TOPIC_DLQ           = "email_dlq"       # Dead Letter Queue — failed events land here

# ── Consumer group IDs ────────────────────────────────────────────────────────
CG_GMAIL_FETCH   = "es-gmail-fetch"
CG_OUTLOOK_FETCH = "es-outlook-fetch"
CG_SMTP_FETCH    = "es-smtp-fetch"
CG_NORMALIZE     = "es-normalize"
CG_FILTER_DEDUP  = "es-filter-dedup"
CG_STORAGE       = "es-storage"
CG_AI_HANDOFF    = "es-ai-handoff"
CG_DLQ_MONITOR   = "es-dlq-monitor"

# ── Kafka connection ──────────────────────────────────────────────────────────
# NOTE: No separate Kafka broker needed.
# The emailservice uses Redis Streams on the existing Upstash Redis instance.
# All stream names below map directly to Redis Stream keys.
# Connection is handled by shared.cache (KAFKA_URL in .env).
KAFKA_BOOTSTRAP_SERVERS = ""   # unused — kept for backward compat only
KAFKA_SASL_USERNAME     = ""
KAFKA_SASL_PASSWORD     = ""
KAFKA_USE_SASL          = False

# ── Topic config (Redis Stream settings) ─────────────────────────────────────
KAFKA_NUM_PARTITIONS = 1     # Redis Streams: single stream, consumer groups handle parallelism
KAFKA_REPLICATION    = 1     # Upstash handles replication internally
KAFKA_RETENTION_MS   = 86_400_000   # 24h (enforced via MAXLEN trim)

# ── Producer / Consumer tuning (Redis Streams) ───────────────────────────────
STREAM_MAXLEN               = 10_000    # trimmed aggressively — free tier 256MB limit
CONSUMER_MAX_POLL_RECORDS   = 100       # messages per XREADGROUP call
CONSUMER_SESSION_TIMEOUT_MS = 30_000    # idle reclaim threshold (ms)
CONSUMER_HEARTBEAT_MS       = 10_000    # unused — kept for interface compat
CONSUMER_AUTO_OFFSET_RESET  = "earliest"  # "0" in Redis Streams terms

# ── Worker batch sizes ────────────────────────────────────────────────────────
FETCH_BATCH_SIZE    = 50
PROCESS_BATCH_SIZE  = 100
WORKER_CONCURRENCY  = 8     # max concurrent async tasks per worker process

# ── User Aggregation Buffer (smart batching) ──────────────────────────────────
# Buffer events per user for this window before processing → 70-80% API reduction
BUFFER_FLUSH_INTERVAL_S = 2.0    # flush after 2 seconds of inactivity — was 3s
BUFFER_MAX_SIZE         = 20     # flush immediately if buffer hits this size
BUFFER_MAX_WAIT_S       = 4.0    # hard max wait — was 5s

# ── Priority system ───────────────────────────────────────────────────────────
PRIORITY_CRITICAL = 0   # VIP / important contacts → instant processing
PRIORITY_HIGH     = 1   # normal business email
PRIORITY_MEDIUM   = 2   # newsletters with replies, etc.
PRIORITY_LOW      = 3   # promotions, low-value (delayed 30-60s)

PRIORITY_LOW_DELAY_S = 45   # delay before processing LOW priority events

# ── Hot user detection ────────────────────────────────────────────────────────
HOT_USER_EMAILS_PER_MIN = 10    # above this → mark as HOT
HOT_USER_CONCURRENCY    = 4     # dedicated semaphore slots for HOT users

# ── Rate limiting (token bucket) ─────────────────────────────────────────────
# Gmail: 250 quota units/user/day, ~10 units per message fetch
RATE_GMAIL_PER_USER_PER_SEC  = 2.0   # max 2 History API calls/sec per user
RATE_GMAIL_GLOBAL_PER_SEC    = 200.0  # global Gmail API cap across all users
RATE_OUTLOOK_PER_USER_PER_SEC = 1.0
RATE_OUTLOOK_GLOBAL_PER_SEC  = 100.0

# ── Backpressure (adaptive) ───────────────────────────────────────────────────
BACKPRESSURE_LAG_THRESHOLD  = 50_000   # start slowing at this lag
BACKPRESSURE_LAG_CRITICAL   = 200_000  # aggressive throttle above this
BACKPRESSURE_MIN_SLEEP_S    = 0.1
BACKPRESSURE_MAX_SLEEP_S    = 30.0

# ── DLQ retry policy ─────────────────────────────────────────────────────────
DLQ_MAX_RETRIES = 3     # move to DLQ after this many failures

# ── Dedup ─────────────────────────────────────────────────────────────────────
DEDUP_BLOOM_CAPACITY   = 10_000_000
DEDUP_BLOOM_ERROR_RATE = 0.001
DEDUP_BUCKET_HOURS     = 24
DEDUP_ENVELOPE_TTL     = 600    # pubsub envelope dedup TTL (seconds)

# ── Idempotency cache ─────────────────────────────────────────────────────────
IDEMPOTENCY_CACHE_SIZE = 500_000   # in-process LRU cache entries
IDEMPOTENCY_TTL_S      = 3600      # 1h — covers Kafka retry window

# ── Gmail watch ───────────────────────────────────────────────────────────────
WATCH_RENEW_BEFORE_HOURS = 24
WATCH_MAX_EXPIRY_DAYS    = 7

# ── SMTP smart polling ────────────────────────────────────────────────────────
SMTP_POLL_ACTIVE_SECS   = 60
SMTP_POLL_INACTIVE_SECS = 300
SMTP_ACTIVE_THRESHOLD   = 3600

# ── Startup warm-up ───────────────────────────────────────────────────────────
WARMUP_ENABLED      = False   # disabled — unnecessary for low-load / free tier
WARMUP_STAGES       = [0.10, 0.30, 0.60, 1.00]
WARMUP_STAGE_SECS   = 30

# ── Metrics ───────────────────────────────────────────────────────────────────
METRICS_ENABLED     = True
METRICS_PORT        = 9090   # Prometheus scrape port

# ── DB write optimization ─────────────────────────────────────────────────────
DB_WRITE_BATCH_SIZE = 200    # rows per bulk INSERT
DB_CONV_BATCH_SIZE  = 50     # conversations per bulk upsert

# ── Service port ──────────────────────────────────────────────────────────────
SERVICE_PORT = 8004

# ── Circuit breaker ───────────────────────────────────────────────────────────
CB_FAILURE_THRESHOLD = 0.5    # 50% failure rate → OPEN
CB_WINDOW            = 20     # sliding window (calls)
CB_RESET_TIMEOUT_S   = 60.0   # seconds before HALF_OPEN probe
CB_MIN_CALLS         = 5      # minimum calls before evaluating

# ── Write-ahead buffer ────────────────────────────────────────────────────────
WRITE_BUFFER_FLUSH_MS  = 75      # flush every 75ms
WRITE_BUFFER_MAX_ROWS  = 2_000   # force-flush above this
WRITE_BUFFER_MAX_FLUSH = 500     # max rows per flush call

# ── SLA tiers ─────────────────────────────────────────────────────────────────
SLA_FREE       = "free"
SLA_PREMIUM    = "premium"
SLA_ENTERPRISE = "enterprise"

# ── Cross-user domain batching ────────────────────────────────────────────────
DOMAIN_BATCH_WINDOW_S  = 0.5   # flush domain batches every 500ms — was 2s
DOMAIN_BATCH_MAX_USERS = 10    # max users per domain batch

# ── Predictive fetch suppression ─────────────────────────────────────────────
FETCH_SUPPRESS_INACTIVE_HOURS = 2    # suppress fetch for users inactive > 2h
FETCH_SUPPRESS_LOW_PRIORITY   = True # suppress LOW priority for inactive users
FETCH_SUPPRESS_DELAY_S        = 120  # delay suppressed fetches by 2 min

# ── Dynamic config ────────────────────────────────────────────────────────────
DYNAMIC_CONFIG_ENABLED  = True
DYNAMIC_CONFIG_REFRESH_S = 300   # 5 minutes — was 30s

# ── Watch heartbeat watchdog ──────────────────────────────────────────────────
WATCH_HEARTBEAT_INTERVAL_S   = 3600   # check every hour
WATCH_INACTIVITY_THRESHOLD_S = 7200   # re-register if silent for 2h

# ── IMAP IDLE ─────────────────────────────────────────────────────────────────
IMAP_IDLE_TIMEOUT_S    = 1740   # 29 min (RFC 2177 recommends < 30 min)
IMAP_RECONNECT_DELAY_S = 30     # delay before reconnecting after error

# ── Durable store-ready queue ─────────────────────────────────────────────────
STORE_RETRY_MAX          = 10   # max DB write retries before DLQ
STORE_RETRY_BASE_DELAY_S = 1.0  # exponential backoff base

# ── AI events stream (async handoff) ─────────────────────────────────────────
AI_EVENTS_MAXLEN = 50_000       # automation-service consumes this directly

# ── Shard-aware routing ───────────────────────────────────────────────────────
STREAM_N_SHARDS = 1             # increase to 4+ when scaling horizontally

# ── SLA worker pools ──────────────────────────────────────────────────────────
SLA_PRIORITY_THRESHOLD = 2      # priorities 0,1 → fast pool; 2,3 → standard pool
