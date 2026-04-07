# emailservice — Architecture Reference

**Version:** 2.0.0  
**Port:** 8004  
**Gateway prefix:** `/email-service`

---

## 1. Overview

emailservice is a standalone FastAPI service that ingests emails from Gmail (Pub/Sub), Outlook (Graph API), and SMTP/IMAP accounts, normalises them, and stores them in PostgreSQL. It exposes a REST inbox API consumed by the frontend and forwards incoming messages to the automation service.

The defining architectural principle is **zero idle cost**: Redis is never polled when no emails are arriving. Processing is triggered exclusively by inbound webhooks.

---

## 2. High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│  INBOUND EVENTS                                                     │
│                                                                     │
│  Gmail Pub/Sub ──────────────────────────────────────────────────┐  │
│  Outlook Graph ──────────────────────────────────────────────────┤  │
│  SMTP/IMAP (polled every 60–300s) ──► smtp_events stream ────────┤  │
└──────────────────────────────────────────────────────────────────┼──┘
                                                                   │
                                                    ┌──────────────▼──────────────┐
                                                    │  api/webhooks.py            │
                                                    │  POST /webhooks/gmail       │
                                                    │  POST /webhooks/outlook     │
                                                    │  Returns 200 in < 5ms       │
                                                    └──────────────┬──────────────┘
                                                                   │ asyncio.create_task()
                                                    ┌──────────────▼──────────────┐
                                                    │  pipeline.py                │
                                                    │  process_gmail_event()      │
                                                    │  process_outlook_event()    │
                                                    │                             │
                                                    │  1. Envelope dedup          │
                                                    │  2. Circuit breaker check   │
                                                    │  3. Load account snapshot   │
                                                    │  4. Rate limit              │
                                                    │  5. Refresh OAuth token     │
                                                    │  6. Fetch messages (Gmail   │
                                                    │     History API / Graph)    │
                                                    │  7. Filter + dedup          │
                                                    │  8. Store to PostgreSQL     │
                                                    │  9. Notify automation       │
                                                    └──────────────┬──────────────┘
                                                                   │
                                              ┌────────────────────┼────────────────────┐
                                              │ success            │ failure             │
                                              ▼                    ▼                     │
                                    ┌──────────────────┐  ┌──────────────────┐          │
                                    │  PostgreSQL       │  │  email_queue     │          │
                                    │  es_messages      │  │  (Redis Stream)  │          │
                                    │  es_conversations │  └────────┬─────────┘          │
                                    └──────────────────┘           │ wakes               │
                                                                    ▼                     │
                                                         ┌──────────────────┐            │
                                                         │  RecoveryWorker  │            │
                                                         │  (event-driven,  │            │
                                                         │  zero idle cost) │            │
                                                         └──────────────────┘            │
```

---

## 3. Component Inventory

### 3.1 Entry Point

**`main.py`** — FastAPI application, port 8004.

Startup sequence:
1. `init_database()` — async SQLAlchemy engine, pool_size=15
2. `init_redis()` — Upstash Redis (TLS), max_connections=20, socket_timeout=15s
3. `_create_tables()` — `CREATE TABLE IF NOT EXISTS` for all three tables; drops `content_html` column if it still exists
4. `ensure_topics()` — creates `email_queue` stream, deletes all legacy stream keys
5. `WatchManager().sync_all_watches()` — renews Gmail/Outlook subscriptions (3s delay)
6. `HistoryRecoveryWorker.run_once()` — catches messages missed during downtime (12s delay)
7. `SmtpPoller().run()` — background SMTP polling loop (20s delay)
8. `RecoveryWorker().start()` — event-driven recovery (2s delay)

Shutdown sequence: stop RecoveryWorker → close HTTP client → close HistoryRecoveryWorker → close DB → close Redis.

Routers mounted: `webhooks`, `connect`, `inbox`, `send_reply`, `accounts`.

---

### 3.2 API Layer (`api/`)

| File | Prefix | Key endpoints |
|---|---|---|
| `webhooks.py` | `/webhooks` | `POST /gmail`, `POST /outlook` |
| `connect.py` | `/email/connect` | `POST /` (OAuth + SMTP setup) |
| `inbox.py` | `/email/inbox` | `GET /threads`, `GET /threads/{id}`, `POST /threads/{id}/read` |
| `send_reply.py` | `/email` | `POST /send-reply` |
| `accounts.py` | `/email/accounts` | `GET /`, `DELETE /{id}` |
| `health.py` | — | `GET /health` |

**`webhooks.py`** — The critical hot path. Decodes the Pub/Sub envelope, spawns `asyncio.create_task(_handle_gmail(...))`, and returns `{"status": "accepted"}` immediately. The background task calls `pipeline.process_gmail_event()`. On failure it calls `push_to_recovery()`. No Redis commands on the happy path.

**`connect.py`** — Calls `EmailConnectionService.connect_and_save()`, then `WatchManager().ensure_watch()` to register the Gmail/Outlook subscription. Returns account metadata.

**`inbox.py`** — Reads directly from `es_messages` and `es_conversations`. Fetches last 20 messages per thread dynamically (no JSONB arrays). Supports pagination via `limit`/`offset`.

**`send_reply.py`** — Sends via Gmail API / SMTP / Outlook Graph. Deduplicates via Redis key `es:sent:{account_id}:{in_reply_to}` (TTL 24h). Stores outgoing message in `es_messages`. Respects `daily_send_limit`.

---

### 3.3 Processing Pipeline (`pipeline.py`)

The core of the v2 architecture. Called directly from webhook handlers — no Redis Stream in the normal path.

**`process_gmail_event(pubsub_id, email_address, history_id) → bool`**

```
1. idempotency.check_and_mark("pubsub", pubsub_id)
   → skip if already processed (in-process LRU, 1h TTL)

2. circuit_breaker("gmail").allow_request()
   → return False if OPEN (caller queues for recovery)

3. token_cache.get_account_snapshot(email_address)
   → L1 (in-process, 300s) → L2 (Redis GET, TTL=token_expiry) → L3 (PostgreSQL)

4. rate_limiter.acquire_gmail(user_id)
   → token bucket, in-process, no Redis

5. token_cache.get_fresh_token(snap)
   → decrypt stored token; refresh via OAuth if expired < 5min
   → persist new token to DB + invalidate Redis cache

6. Gmail History API: GET /users/me/history?startHistoryId=...
   → paginated, historyTypes=messageAdded

7. idempotency.check_and_mark("gmail_msg", message_id) for each ID
   → skip already-seen message IDs

8. Fetch full messages concurrently (semaphore=5)
   → GET /users/me/messages/{id}?format=full
   → skip DRAFT/TRASH/SPAM labels

9. email_filter.should_filter(subject, from_email)
   → skip bounces, noreply senders, OTP subjects

10. dedup.is_duplicate(message_id) / dedup.mark_seen(message_id)
    → Bloom filter (in-process, 10M capacity, 0.1% error rate)

11. _store_message() → PostgreSQL
    → INSERT es_messages ON CONFLICT DO NOTHING
    → UPSERT es_conversations (update last_message_id, message_count)

12. _notify_automation() → HTTP POST to automation service
    → fire-and-forget, failure is silent

13. token_cache.advance_history_cursor(account_id, history_id, email)
    → UPDATE email_accounts SET last_history_id = ?
    → invalidate Redis snap cache
```

Returns `True` on success, `False` on transient failure (circuit open, API 5xx, exception). The webhook handler calls `push_to_recovery()` on `False`.

**`process_outlook_event(subscription_id, message_id) → bool`** — Same pattern: resolve account → fetch token → fetch message via Graph API → filter → store → notify.

**Shared HTTP client** — Single `httpx.AsyncClient` (HTTP/2, max_connections=50, keepalive=10). Created lazily, closed on shutdown.

---

### 3.4 Recovery System (`workers/recovery_worker.py`)

**Zero idle cost.** The worker sleeps on `asyncio.Event` — a pure Python primitive that costs nothing. It only wakes when `push_to_recovery()` is called.

```
push_to_recovery(event_type, payload)
  → XADD email_queue {type, data}   (1 Redis command)
  → _wake_event.set()               (in-process signal)

RecoveryWorker._event_loop()
  → await _wake_event.wait()        (sleeping, 0 Redis commands)
  → _wake_event.clear()
  → _drain_redis()
      → XRANGE email_queue - + COUNT 100
      → for each message: process_event() → XDEL on success
  → _drain_memory()                 (in-memory fallback queue)
  → sleep again
```

On startup: `_drain_redis()` runs once to catch any events left from a previous crash (1 `XRANGE` command).

Uses `XRANGE`/`XDEL` instead of `XREADGROUP` — no consumer group overhead, no `XAUTOCLAIM` needed.

Fallback: if Redis is unavailable during `push_to_recovery()`, the event goes to `_in_memory_queue` (asyncio.Queue). Processed on next wake.

---

### 3.5 Background Workers

**`HistoryRecoveryWorker`** (`workers/history_recovery_worker.py`)

Runs once on startup (12s delay), then every 6 days. Fetches all messages since `last_history_id` for each active Gmail account — catches emails missed during downtime. Uses half-weight rate limit tokens to avoid competing with live processing. Debounce: skips accounts synced within the last 5 minutes (`es:recovery:debounce:{account_id}`, TTL 300s).

**`WatchManager`** (`workers/watch_manager.py`)

Registers and renews Gmail Pub/Sub watches (7-day expiry, renews 24h before). Registers and renews Outlook Graph subscriptions (4230-minute expiry). Runs on startup and when a new account connects.

**`SmtpPoller`** (`workers/smtp_fetch_worker.py`)

Polls SMTP/IMAP accounts on a schedule: active users (last message < 1h) every 60s, inactive every 300s. Publishes `smtp_events` to Redis Stream. `SmtpFetchWorker` consumes those events and fetches IMAP messages via blocking I/O in a thread executor.

**Legacy stream workers** (`GmailFetchWorker`, `OutlookFetchWorker`, `FilterDedupWorker`, `StorageWorker`, `AIHandoffWorker`) — present in the codebase but **not started** in `main.py`. Replaced by `pipeline.py` for Gmail/Outlook. The SMTP path still uses `SmtpFetchWorker` via the stream.

**`BaseWorker`** (`workers/base_worker.py`) — Abstract base for stream consumers. Uses `XREADGROUP block=8000ms`. Idle cost: 1 Redis command per 8s. ACKs after successful processing; sends to DLQ on persistent failure.

**`LoadBalancer`** (`workers/load_balancer.py`) — Monitors stream lag via `XINFO GROUPS` every 5 minutes. Emits in-process backpressure signals. SLA tier routing: CRITICAL/HIGH → small batches, LOW → large batches.

---

### 3.6 Data Models (`models/`)

**`EmailAccount`** — Shared with other services. Stores OAuth tokens (AES-256-GCM encrypted), SMTP credentials, Gmail watch state (`last_history_id`, `watch_expiry`), and account status.

**`EmailMessage`** (`es_messages`) — Append-only, one row per message. No JSONB message arrays. Columns: `message_id`, `thread_id`, `user_id`, `email_account_id`, `provider`, `from_email`, `to_emails` (JSONB), `cc_emails` (JSONB), `subject`, `content` (plain text only, HTML never stored), `timestamp`, `direction`, `status`, `is_read`, `has_attachments`, `metadata` (JSONB). Unique constraint: `(user_id, message_id)`.

**`EmailConversation`** (`es_conversations`) — One row per thread, upserted on each new message. Columns: `thread_id`, `user_id`, `email_account_id`, `provider`, `subject`, `participants` (JSONB), `message_count`, `last_message_id`, `last_message_at`, `is_read`, `status`, plus AI fields (`summary`, `intent_type`, `priority_score`, `lead_status`) and business fields (`follow_up_required`, `tags`). Unique constraint: `(user_id, thread_id)`.

---

### 3.7 Support Modules

**`token_cache.py`** — 3-layer account snapshot cache.
- L1: in-process dict, TTL=300s, zero latency
- L2: Redis `GET es:snap:{email}`, TTL aligned with token expiry (max 1h)
- L3: PostgreSQL `SELECT * FROM email_accounts WHERE email_address = ?`
- `get_fresh_token()`: decrypts stored token; if expired within 5 minutes, calls OAuth refresh endpoint, persists new token to DB, invalidates L1+L2

**`dedup.py`** — Time-bucketed Bloom filter. Two 24h buckets active simultaneously (current + previous). Capacity 10M entries, 0.1% false positive rate, ~17MB per bucket. Zero Redis commands. DB unique constraint is the authoritative safety net.

**`idempotency.py`** — In-process LRU cache with TTL. Max 500K entries, 1h TTL. Thread-safe via `threading.Lock`. `check_and_mark(provider, message_id)` is atomic. Zero Redis commands.

**`email_filter.py`** — Conservative pre-filter. Only rejects clearly automated system messages: delivery failures, mailer-daemon senders, noreply senders, OTP subjects. Does not filter newsletters or promotions (user's choice).

**`circuit_breaker.py`** — Per-provider sliding-window circuit breaker. Failure threshold 50%, window 20 calls, reset timeout 60s. States: CLOSED → OPEN → HALF_OPEN. Prevents cascading failures when Gmail/Outlook APIs degrade.

**`rate_limiter.py`** — Token bucket rate limiter. Per-user (2 Gmail calls/sec) and global (200 Gmail calls/sec). In-process, no Redis. `wait_and_acquire()` sleeps if quota exceeded.

**`dynamic_config.py`** — Live config tuning via Redis. Reads `es:config:{KEY}` every 5 minutes. Falls back to `config.py` static values if Redis unavailable or key missing.

**`user_buffer.py`** — Event aggregation buffer. Groups Pub/Sub events per user for 2–4s before processing, reducing Gmail API calls by 70–80%. Priority scoring: CRITICAL (direct reply, VIP domain) → bypass buffer; LOW (newsletters) → delayed 45s. Hot user detection: >10 emails/min gets dedicated semaphore slots.

**`write_buffer.py`** — DB write protection layer. Accumulates rows in memory, flushes every 500ms or when buffer hits 2000 rows. Retry on failure (rows stay in buffer). Used by legacy `StorageWorker` (not by `pipeline.py` which writes directly).

**`encryption.py`** — AES-256-GCM encryption for OAuth tokens and SMTP passwords. Key from `ENCRYPTION_KEY` env var.

**`adapters.py`** — OAuth token exchange and SMTP credential validation. `GmailAdapter`, `OutlookAdapter`, `SMTPAdapter`.

**`connection_service.py`** — Orchestrates account connection: validate credentials → encrypt → save to DB → register watch.

**`schemas.py`** — Pydantic request/response models for the connect API.

**`dependencies.py`** — FastAPI dependency for JWT authentication. Extracts `user_id` from Bearer token.

**`metrics.py`** — Prometheus metrics (falls back to no-ops if `prometheus_client` not installed). Exposed on `:9090/metrics`.

**`stream_client.py`** — Redis Streams adapter. `publish()`, `publish_batch()`, `StreamConsumer` (XREADGROUP, 8s block, XAUTOCLAIM every 5 min). `ensure_streams()` creates `email_queue`, deletes all legacy stream keys.

**`kafka_client.py`** — Compatibility shim. Re-exports `stream_client` functions under original Kafka-style names (`make_consumer`, `ensure_topics`, `publish`, `publish_batch`).

---

## 4. Redis Key Inventory

| Key pattern | Type | TTL | Purpose |
|---|---|---|---|
| `es:snap:{email}` | STRING | token_expiry (max 1h) | Account snapshot cache (L2) |
| `es:env:{pubsub_id}` | STRING | 600s | Gmail Pub/Sub envelope dedup |
| `es:sub:{subscription_id}` | STRING | 4 days | Outlook subscription → account mapping |
| `es:sent:{account_id}:{in_reply_to}` | STRING | 24h | Send dedup |
| `es:smtp:poll:{account_id}` | STRING | 1h | SMTP last-poll timestamp |
| `es:recovery:debounce:{account_id}` | STRING | 300s | History recovery debounce |
| `es:history_recovery:last_run` | STRING | 12 days | Recovery scheduler state |
| `es:config:{KEY}` | STRING | 24h | Dynamic config values |
| `email_queue` | STREAM | no TTL | Crash-recovery buffer (XRANGE/XDEL) |

Legacy keys deleted on startup: `gmail_events`, `outlook_events`, `smtp_events`, `fetch_results`, `store_ready`, `ai_events`, `email_dlq`, `automation_events` (and their `:0`–`:3` shard variants).

---

## 5. Redis Command Budget

| Scenario | Commands | Rate |
|---|---|---|
| Idle (no emails) | 0 | 0/sec |
| Webhook received, success | ~2 (GET snap + SETEX snap on token refresh) | per email |
| Webhook received, failure | 1 XADD | per failure |
| Recovery drain | 1 XRANGE + N XDEL | per wake |
| Startup | 1 XRANGE + N EXISTS/GET (history recovery) | once |
| SMTP poll | 1 GET + 1 SETEX per account | per poll cycle |
| Dynamic config refresh | 1 pipeline (14 GETs) | every 5 min |

**Previous architecture (5 polling workers):** ~10 commands/sec idle = 864,000/day  
**Current architecture:** 0 commands/sec idle = 0/day

---

## 6. PostgreSQL Operations

| Operation | Table | Trigger |
|---|---|---|
| SELECT | `email_accounts` | Token cache miss (L1+L2 miss) |
| UPDATE | `email_accounts` | Token refresh, history cursor advance |
| INSERT ON CONFLICT DO NOTHING | `es_messages` | Every stored message |
| INSERT ON CONFLICT DO UPDATE | `es_conversations` | Every stored message |
| SELECT | `es_messages` | Inbox API reads |
| SELECT | `es_conversations` | Inbox API reads |
| UPDATE | `es_conversations` | Mark thread as read |
| CREATE TABLE IF NOT EXISTS | all | Startup |
| ALTER TABLE DROP COLUMN | `es_messages` | One-time migration (content_html) |

Connection pool: `pool_size=15`, `max_overflow=10`, `timeout=10s`.

---

## 7. External API Calls

| Service | Endpoint | When |
|---|---|---|
| Gmail | `GET /users/me/history` | Per webhook event |
| Gmail | `GET /users/me/messages/{id}` | Per new message ID |
| Gmail | `POST /users/me/watch` | Account connect + renewal |
| Gmail OAuth | `POST /token` | Token refresh |
| Outlook Graph | `GET /me/messages/{id}` | Per webhook event |
| Outlook Graph | `POST /subscriptions` | Account connect + renewal |
| Microsoft OAuth | `POST /{tenant}/oauth2/v2.0/token` | Token refresh |
| Automation service | `POST /ai/process` | Per incoming message (fire-and-forget) |

All external calls use the shared `httpx.AsyncClient` (HTTP/2, connection pooling, 20s read timeout).

---

## 8. Deduplication Layers

Messages pass through four independent dedup layers:

```
1. Pub/Sub envelope dedup (idempotency cache)
   → prevents double-processing same Pub/Sub notification
   → in-process LRU, 1h TTL

2. Message ID dedup (idempotency cache)
   → prevents fetching same message_id twice
   → in-process LRU, 1h TTL

3. Bloom filter dedup (dedup.py)
   → fast pre-filter before DB write
   → in-process, 10M capacity, 0.1% false positive rate

4. DB unique constraint (user_id, message_id)
   → authoritative safety net
   → catches Bloom false positives and cross-process duplicates
```

---

## 9. Failure Handling

| Failure | Behaviour |
|---|---|
| Gmail API 5xx | Circuit breaker records failure; event queued to `email_queue` |
| Gmail API 429 | Sleep 10s; event queued to `email_queue` |
| Gmail API 401/404 | Not retried (auth error / expired history) |
| Circuit breaker OPEN | Event queued to `email_queue` immediately |
| DB write failure | Logged; message lost (Bloom filter prevents re-fetch) |
| Redis unavailable | Token cache falls back to DB; recovery events go to in-memory queue |
| Automation service down | HTTP POST fails silently (non-critical path) |
| Process crash | `email_queue` stream persists; drained on next startup |

---

## 10. Scaling Strategy

**Horizontal scaling:** Add more FastAPI workers (uvicorn `--workers N`). Each process has independent in-process caches (L1 token cache, Bloom filter, idempotency LRU). Redis and PostgreSQL are the shared coordination points.

**At 1,000 users:** Same architecture, same Redis cost. The bottleneck is Gmail API quota (250 units/user/day), not infrastructure.

**At 100,000 users:** Enable `N_SHARDS=4` in `stream_client.py` for the SMTP path. Add read replicas for inbox queries. Consider partitioning `es_messages` by `user_id`.

**At 1,000,000 users:** Separate the SMTP worker into its own process. Add a dedicated Redis instance for streams vs. cache. Consider Upstash QStash for webhook delivery buffering.

---

## 11. Configuration Reference

Key tuning parameters in `config.py`:

| Parameter | Default | Effect |
|---|---|---|
| `BUFFER_FLUSH_INTERVAL_S` | 2.0s | Gmail API call reduction (higher = fewer calls, more latency) |
| `PROCESS_BATCH_SIZE` | 100 | Stream consumer batch size |
| `WORKER_CONCURRENCY` | 8 | Max concurrent async tasks per worker |
| `RATE_GMAIL_GLOBAL_PER_SEC` | 200 | Global Gmail API cap |
| `RATE_GMAIL_PER_USER_PER_SEC` | 2.0 | Per-user Gmail API cap |
| `DEDUP_BLOOM_CAPACITY` | 10,000,000 | Bloom filter capacity (10M messages/24h) |
| `IDEMPOTENCY_CACHE_SIZE` | 500,000 | In-process LRU max entries |
| `SMTP_POLL_ACTIVE_SECS` | 60 | SMTP poll interval for active users |
| `SMTP_POLL_INACTIVE_SECS` | 300 | SMTP poll interval for inactive users |
| `WATCH_RENEW_BEFORE_HOURS` | 24 | Renew Gmail watch this many hours before expiry |
| `DYNAMIC_CONFIG_REFRESH_S` | 300 | How often to re-read config from Redis |

Live tuning (no restart required):
```
SET es:config:PROCESS_BATCH_SIZE 150
SET es:config:RATE_GMAIL_GLOBAL_PER_SEC 150
```

---

## 12. File Map

```
emailservice/
├── main.py                          Application entry point, lifespan management
├── config.py                        All configuration constants
├── pipeline.py                      Direct webhook processing (core v2 logic)
├── stream_client.py                 Redis Streams adapter (XREADGROUP, XADD, etc.)
├── kafka_client.py                  Compatibility shim over stream_client
├── token_cache.py                   3-layer account snapshot + token cache
├── dedup.py                         Time-bucketed Bloom filter dedup
├── idempotency.py                   In-process LRU idempotency cache
├── email_filter.py                  Conservative email pre-filter
├── circuit_breaker.py               Per-provider circuit breaker
├── rate_limiter.py                  Token bucket rate limiter
├── dynamic_config.py                Live config from Redis
├── user_buffer.py                   Event aggregation buffer + priority scoring
├── write_buffer.py                  DB write protection layer (legacy workers)
├── encryption.py                    AES-256-GCM token encryption
├── adapters.py                      OAuth + SMTP credential adapters
├── connection_service.py            Account connection orchestration
├── schemas.py                       Pydantic request/response models
├── dependencies.py                  JWT auth dependency
├── metrics.py                       Prometheus metrics
├── api/
│   ├── webhooks.py                  Gmail Pub/Sub + Outlook Graph endpoints
│   ├── connect.py                   Account connection endpoints
│   ├── inbox.py                     Inbox read endpoints
│   ├── send_reply.py                Email send endpoint
│   ├── accounts.py                  Account management endpoints
│   └── health.py                    Health check endpoint
├── workers/
│   ├── base_worker.py               Abstract stream consumer base class
│   ├── recovery_worker.py           Event-driven crash recovery (zero idle cost)
│   ├── history_recovery_worker.py   Startup + 6-day gap recovery
│   ├── watch_manager.py             Gmail/Outlook subscription management
│   ├── smtp_fetch_worker.py         SMTP/IMAP fetch + SmtpPoller
│   ├── gmail_fetch_worker.py        Legacy Gmail stream worker (not started)
│   ├── outlook_fetch_worker.py      Legacy Outlook stream worker (not started)
│   ├── filter_dedup_worker.py       Legacy filter/dedup stream worker (not started)
│   ├── storage_worker.py            Legacy storage stream worker (not started)
│   ├── ai_handoff_worker.py         Legacy AI handoff stream worker (not started)
│   └── load_balancer.py             Stream lag monitor + backpressure signals
└── models/
    ├── email_account.py             EmailAccount ORM model (shared table)
    ├── messages.py                  EmailMessage ORM model (es_messages)
    └── conversations.py             EmailConversation ORM model (es_conversations)
```
