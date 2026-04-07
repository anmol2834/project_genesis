# emailservice — Complete Architecture Reference
> Version 2.0.0 | Port 8004 | Replaces email-service entirely

---

## 1. System Overview

emailservice is a fully standalone, enterprise-grade email ingestion and processing service built for 1 million concurrent users. It replaces the old email-service (Celery + Redis queues + JSONB storage) with a Redis Streams pipeline, normalized append-only DB tables, and a layered dedup + rate-limiting system.

**Zero dependency on email-service.** All code is self-contained. email-service is kept only as a reference until emailservice is fully validated in production.

**Gateway integration:** The gateway-service routes all `/email-service/*` requests to `http://localhost:8004`. emailservice runs on the same port and responds to the same path prefixes — it is a transparent drop-in replacement.

---

## 2. Complete Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                        INGESTION LAYER                              │
│                                                                     │
│  Gmail Pub/Sub ──→ POST /webhooks/gmail  ──→ XADD gmail_events     │
│  Outlook Graph ──→ POST /webhooks/outlook ──→ XADD outlook_events  │
│  SMTP/IMAP     ──→ SmtpPoller (bg task)  ──→ XADD smtp_events      │
│                                                                     │
│  Webhook response: < 5ms. Zero API calls. Zero DB writes.          │
└─────────────────────────────────────────────────────────────────────┘
                              ↓ Redis Streams (XREADGROUP)
┌─────────────────────────────────────────────────────────────────────┐
│                         FETCH LAYER                                 │
│                                                                     │
│  GmailFetchWorker   consumes gmail_events                          │
│    → UserAggregationBuffer (3-5s window per user)                  │
│    → N Pub/Sub events → 1 Gmail History API call (70-80% savings)  │
│    → Token bucket rate limiter (per-user + global)                 │
│    → Hot user isolation (dedicated semaphore slots)                │
│    → Concurrent message fetch (up to 10 parallel per user)         │
│    → Cursor advances ONLY after successful publish                 │
│                                                                     │
│  OutlookFetchWorker consumes outlook_events                        │
│    → Resolves account from subscription_id (Redis cache)           │
│    → Fetches full message via Graph API                            │
│    → Per-message dedup via Redis SET NX                            │
│                                                                     │
│  SmtpFetchWorker    consumes smtp_events                           │
│    → IMAP FETCH UNSEEN (blocking I/O in thread pool)               │
│    → Max 50 messages per poll cycle                                │
│                                                                     │
│  All workers publish to: fetch_results                             │
└─────────────────────────────────────────────────────────────────────┘
                              ↓ Redis Streams
┌─────────────────────────────────────────────────────────────────────┐
│                      FILTER + DEDUP LAYER                          │
│                                                                     │
│  FilterDedupWorker  consumes fetch_results                         │
│                                                                     │
│  Dedup (3 layers, fastest first):                                  │
│    1. In-process LRU idempotency cache (provider:message_id, 1h)   │
│    2. Time-bucketed Bloom filter (10M cap, 0.1% FP, 24h buckets)   │
│    3. DB UniqueConstraint (safety net, catches cross-process FP)   │
│                                                                     │
│  Filter (synchronous, zero I/O):                                   │
│    - Spam / OTP / promotional / automated sender patterns          │
│    - No-reply addresses, bank statements, delivery failures        │
│    - Promo domains (amazon, linkedin, naukri, etc.)                │
│                                                                     │
│  Enrichment:                                                       │
│    - Direction detection (incoming vs outgoing)                    │
│    - Participants list (from + to + cc)                            │
│    - Priority scoring (CRITICAL / HIGH / MEDIUM / LOW)             │
│    - Schema version tag (_schema_version: 2)                       │
│                                                                     │
│  Publishes survivors to: store_ready                               │
└─────────────────────────────────────────────────────────────────────┘
                              ↓ Redis Streams
┌─────────────────────────────────────────────────────────────────────┐
│                        STORAGE LAYER                               │
│                                                                     │
│  StorageWorker      consumes store_ready                           │
│                                                                     │
│  DB writes (bulk, single round-trip each):                         │
│    1. Bulk INSERT es_messages (ON CONFLICT DO NOTHING)             │
│       - Chunked at 200 rows to avoid PG param limit                │
│       - Append-only: never rewrites existing rows                  │
│    2. Bulk UPSERT es_conversations (ON CONFLICT DO UPDATE)         │
│       - One SQL statement for all threads in the batch             │
│       - Returns conversation UUIDs via RETURNING clause            │
│                                                                     │
│  Publishes incoming messages to: ai_events                         │
└─────────────────────────────────────────────────────────────────────┘
                              ↓ Redis Streams
┌─────────────────────────────────────────────────────────────────────┐
│                       AI HANDOFF LAYER                             │
│                                                                     │
│  AIHandoffWorker    consumes ai_events                             │
│                                                                     │
│  Processing:                                                       │
│    - Dedup by conversation_id (keep highest priority per conv)     │
│    - Sort by priority (CRITICAL first)                             │
│    - Idempotency check (LRU cache, 1h TTL)                         │
│                                                                     │
│  Primary path:  XADD automation_events → automation-service       │
│  Fallback path: POST /ai/process (HTTP, backward compat)           │
│                                                                     │
│  Zero blocking: email ingestion never waits for AI                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Redis Streams (Queue System)

Replaces Celery + Redis queues entirely. Uses the existing Upstash Redis instance.

### Stream Topology

| Stream | Producer | Consumer Group | Consumer Worker |
|--------|----------|----------------|-----------------|
| `gmail_events` | Webhook `/webhooks/gmail` | `es-gmail-fetch` | GmailFetchWorker |
| `outlook_events` | Webhook `/webhooks/outlook` | `es-outlook-fetch` | OutlookFetchWorker |
| `smtp_events` | SmtpPoller | `es-smtp-fetch` | SmtpFetchWorker |
| `fetch_results` | Fetch workers | `es-filter-dedup` | FilterDedupWorker |
| `store_ready` | FilterDedupWorker | `es-storage` | StorageWorker |
| `ai_events` | StorageWorker | `es-ai-handoff` | AIHandoffWorker |
| `automation_events` | AIHandoffWorker | (automation-service) | — |
| `email_dlq` | BaseWorker (on failure) | `es-dlq-monitor` | — |

### Key Properties
- **XADD with MAXLEN ~500K** — streams auto-trim, preventing memory blow-up
- **XREADGROUP** — consumer groups guarantee each message delivered to exactly one consumer
- **XACK after processing** — manual commit, exactly-once semantics
- **XAUTOCLAIM** — reclaims messages idle >60s from crashed workers (crash recovery)
- **Pipeline XADD** — `publish_batch()` uses a single Redis pipeline round-trip for entire batch
- **Sync client on hot path** — `get_redis_client()` (no await) used in publish/consume, not `await get_redis()`

### Backpressure
- `BaseWorker._update_backpressure()` checks `XINFO GROUPS` pending count every 10s (throttled)
- Lag > 50K → proportional sleep + batch size reduction
- Lag > 200K → max sleep (30s) + halve batch size
- Lag decreasing → gradually grow batch size back to max

---

## 4. Database Schema

### `email_accounts` (unchanged from email-service)
Stores connected email accounts. Schema must never be modified — shared with email-service during migration.

Key fields: `id`, `user_id`, `email_address`, `provider`, `access_token` (AES-256 encrypted), `refresh_token` (encrypted), `token_expiry`, `last_history_id` (Gmail cursor), `watch_expiry`, `daily_send_limit`, `daily_sent_count`

### `es_messages` (new — append-only)
One row per email message. Never rewritten.

| Column | Type | Notes |
|--------|------|-------|
| `message_id` | String(512) | Provider message ID |
| `thread_id` | String(512) | Provider thread/conversation ID |
| `user_id` | UUID | Multi-tenant isolation |
| `email_account_id` | UUID | Which account received it |
| `provider` | String | gmail / outlook / smtp |
| `from_email` | Text | Sender address |
| `to_emails` | JSONB | Recipient list |
| `cc_emails` | JSONB | CC list |
| `subject` | Text | Email subject |
| `content` | Text | Cleaned plain-text body |
| `content_html` | Text | Original HTML |
| `timestamp` | DateTime | Email send/receive time (UTC) |
| `direction` | Enum | incoming / outgoing |
| `status` | Enum | received / sent / failed / queued |
| `is_read` | Boolean | Read status |
| `has_attachments` | Boolean | Attachment flag |
| `metadata` | JSONB | label_ids, snippet, etc. |

**Indexes:** `(user_id, thread_id, timestamp)`, `(user_id, is_read, timestamp)`, `(user_id, direction, timestamp)`, `(email_account_id, timestamp)`

**Dedup constraint:** `UNIQUE(user_id, message_id)` — DB-level safety net

### `es_conversations` (new — upserted per thread)
One row per email thread. No embedded message arrays.

| Column | Type | Notes |
|--------|------|-------|
| `thread_id` | String(512) | Provider thread ID |
| `user_id` | UUID | Multi-tenant isolation |
| `subject` | Text | Thread subject |
| `participants` | JSONB | All email addresses in thread |
| `message_count` | Integer | Total messages (incremented on upsert) |
| `last_message_id` | String | Latest message_id |
| `last_message_at` | DateTime | For inbox sorting |
| `is_read` | Boolean | Unread indicator |
| `status` | String | active / archived / snoozed |
| `summary` | Text | AI-generated summary |
| `intent_type` | String | support / sales / inquiry / complaint |
| `priority_score` | Float | 0.0 – 1.0 |
| `lead_status` | Enum | hot / warm / cold |
| `follow_up_required` | Boolean | Business flag |
| `tags` | JSONB | Custom tags |

**AI context query:** `SELECT * FROM es_messages WHERE thread_id=X ORDER BY timestamp DESC LIMIT N` — no JSONB arrays, no row rewrites.

---

## 5. Dedup System (3 Layers)

### Layer 1 — In-process LRU Idempotency Cache (`idempotency.py`)
- Key: `provider:message_id` (e.g. `gmail:18f3a2b1c4d5`)
- Storage: `OrderedDict` with TTL (1h), max 500K entries
- Thread-safe via `threading.Lock`
- Evicts oldest on overflow (LRU)
- ~0ms lookup — no network, no I/O
- Handles 99.9% of duplicates from Kafka retries

### Layer 2 — Time-bucketed Bloom Filter (`dedup.py`)
- Two 24h buckets (current + previous), auto-rotating
- Capacity: 10M entries per bucket, ~17MB RAM each
- False positive rate: 0.1% (acceptable — Layer 3 catches them)
- Hash: MurmurHash3 (mmh3) — fast, uniform distribution
- Per-process (no cross-process sharing needed — Layer 3 handles that)

### Layer 3 — DB Unique Constraint
- `UNIQUE(user_id, message_id)` on `es_messages`
- `INSERT ON CONFLICT DO NOTHING` — silent dedup at DB level
- Authoritative: catches any false positives from Layers 1 & 2
- Also catches cross-process duplicates (multiple worker instances)

### Envelope Dedup (Gmail only)
- Key: `es:env:{pubsub_id}` in Redis, TTL 600s
- Prevents the same Pub/Sub notification from being processed twice
- Claimed in GmailFetchWorker before any API call
- Released on transient errors so Pub/Sub can retry

---

## 6. Rate Limiting (`rate_limiter.py`)

Token bucket algorithm — async-safe, non-blocking, pure in-process.

### Levels
1. **Per-user Gmail limit:** 2 calls/sec per user (burst: 10s worth)
2. **Global Gmail limit:** 200 calls/sec across all users (burst: 600)
3. **Per-user Outlook limit:** 1 call/sec per user
4. **Global Outlook limit:** 100 calls/sec

### Behavior
- `wait_and_acquire()` sleeps via `asyncio.sleep()` — never blocks the event loop
- Tokens refill continuously (not in discrete intervals)
- Per-user buckets created on demand, evicted when user goes inactive
- Recovery worker uses 0.5 token weight — doesn't compete with live fetch

---

## 7. User Aggregation Buffer (`user_buffer.py`)

Solves the core Gmail API cost problem: each Pub/Sub notification triggering a separate History API call.

### How it works
1. GmailFetchWorker feeds each Pub/Sub event into the buffer keyed by `email_address`
2. Buffer holds events for 3-5 seconds (configurable)
3. On flush: all buffered events for a user → single History API call
4. Result: 5 Pub/Sub events → 1 API call = 80% API cost reduction

### Flush triggers (whichever comes first)
- Time threshold: 3s inactivity (HIGH/MEDIUM priority), 5s (LOW)
- Size threshold: 20 events accumulated
- Hard deadline: 5s max wait
- CRITICAL priority: bypass buffer entirely, process immediately

### Priority levels
| Level | Value | Trigger | Delay |
|-------|-------|---------|-------|
| CRITICAL | 0 | Reply to our outgoing message, VIP domain | Immediate |
| HIGH | 1 | Normal business email, existing thread | 3s buffer |
| MEDIUM | 2 | New conversation | 3s buffer |
| LOW | 3 | Newsletter patterns, promo domains | 5s buffer + 45s delay |

### Hot user detection
- Sliding 60s window per user
- If emails/min > 10 → mark as HOT
- HOT users get dedicated semaphore slots (don't compete with normal users)
- Prevents one high-volume user from starving others

---

## 8. Token Cache (`token_cache.py`)

3-layer cache for account snapshots and OAuth tokens.

```
L1: In-process dict (TTL 5min, zero network cost)
    ↓ miss
L2: Redis (TTL 1h, shared across worker processes)
    ↓ miss
L3: PostgreSQL (authoritative source)
```

Token refresh happens **only in fetch workers** — never in webhook handlers. After refresh, new token is persisted to DB and all cache layers are invalidated.

---

## 9. Background Tasks (in-process)

These run inside the main FastAPI process as `asyncio.create_task()`:

### Watch Sync (startup + on connect)
- Runs 3s after startup
- Calls `WatchManager.sync_all_watches()` for all Gmail/Outlook accounts
- Renews watches expiring within 24h
- Gmail watch: `POST /gmail/v1/users/me/watch` → stores `historyId` + `watch_expiry`
- Outlook subscription: `POST /graph/v1.0/subscriptions` → stores sub_id in Redis

### History Recovery (startup + every 6 days)
- Runs 12s after startup (after watch sync completes)
- Runs once immediately, then schedules `run_forever()` every 6 days
- Redis key `es:history_recovery:last_run` prevents re-running within interval (survives restarts)
- Per-account debounce: 5min Redis key prevents re-scanning same account twice
- Uses half-weight rate limit tokens (doesn't compete with live fetch)
- Publishes recovered messages directly to `fetch_results` (same pipeline as live)

### SMTP Poller (continuous background task)
- Runs 20s after startup as `asyncio.create_task(SmtpPoller().run())`
- Checks every 30s which SMTP accounts need polling
- Active users (last message < 1h): poll every 60s
- Inactive users: poll every 300s
- Publishes `smtp_events` to Redis Streams → SmtpFetchWorker consumes

---

## 10. API Endpoints

### Webhook Endpoints (ultra-fast, < 5ms)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/webhooks/gmail` | Gmail Pub/Sub push receiver |
| GET | `/webhooks/gmail` | Health probe |
| POST | `/webhooks/outlook` | Outlook Graph push receiver + validation handshake |
| GET | `/webhooks/outlook` | Validation probe |
| GET | `/webhooks/health` | Webhook layer health |

### Email Account Management
| Method | Path | Description |
|--------|------|-------------|
| POST | `/email/connect` | Connect Gmail / Outlook / SMTP account |
| GET | `/email/accounts` | List user's connected accounts |
| DELETE | `/email/accounts/{id}` | Disconnect account |

### Inbox
| Method | Path | Description |
|--------|------|-------------|
| GET | `/email/inbox/threads` | Paginated thread list (from es_conversations + es_messages) |
| GET | `/email/inbox/threads/{thread_id}` | Full thread with messages |
| POST | `/email/inbox/threads/{thread_id}/read` | Mark thread as read |

### Send
| Method | Path | Description |
|--------|------|-------------|
| POST | `/email/send-reply` | Send reply via Gmail / Outlook / SMTP |

### Observability
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | DB + Redis health check |
| GET | `/stats` | Live stream lengths, pending counts, table row counts |
| GET | `/` | Service info |

---

## 11. Worker Processes (`run_worker.py`)

Each worker runs as an independent process with its own DB pool, Redis connection, and Bloom filter. A crash in one worker never affects others.

```bash
python run_worker.py gmail_fetch      # 2-4 replicas recommended
python run_worker.py outlook_fetch    # 1-2 replicas
python run_worker.py smtp_fetch       # 1 replica (includes SmtpPoller)
python run_worker.py filter_dedup     # 2-4 replicas
python run_worker.py storage          # 2-4 replicas
python run_worker.py ai_handoff       # 1-2 replicas
python run_worker.py history_recovery # 1 replica (6-day schedule)
python run_worker.py watch_sync       # 1 replica (6-hour schedule)
```

### BaseWorker features (all workers inherit)
- **Warm-up:** batch size starts at 10% of max, grows to 100% over 4 stages (30s each)
- **Adaptive backpressure:** checks stream lag every 10s, adjusts sleep + batch size
- **DLQ:** after 3 failed retries, event moves to `email_dlq` stream
- **Retry:** failed events re-published to same topic with `_retry_count` incremented
- **Graceful shutdown:** drains in-flight batch before stopping, ACKs pending messages
- **Metrics:** Prometheus counters/histograms on every batch (latency, errors, lag)

---

## 12. Encryption

AES-256-GCM symmetric encryption for all sensitive fields.

- Key: `ENCRYPTION_KEY` from `.env` (base64-encoded 32-byte key)
- Nonce: 12 random bytes prepended to ciphertext
- Storage format: `base64(nonce + ciphertext)`
- Fields encrypted: `access_token`, `refresh_token`, `smtp_password`
- Functions: `encrypt(plaintext)` / `decrypt(token)` in `encryption.py`

---

## 13. Gateway Integration

The gateway-service (`server/services/gateway-service/router.py`) routes all `/email-service/*` requests to `http://localhost:8004` with a 300s timeout (for SSE connections).

emailservice runs on port 8004 and handles all the same routes as email-service. No gateway configuration changes needed.

```
Client → Gateway (8000) → /email-service/* → emailservice (8004)
                          strips /email-service prefix
                          forwards to /email/connect, /webhooks/gmail, etc.
```

---

## 14. Configuration Reference (`config.py`)

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVICE_PORT` | 8004 | HTTP port |
| `STREAM_MAXLEN` | 500,000 | Max messages per Redis Stream |
| `CONSUMER_MAX_POLL_RECORDS` | 100 | Messages per XREADGROUP call |
| `FETCH_BATCH_SIZE` | 50 | Max message IDs per History API call |
| `PROCESS_BATCH_SIZE` | 100 | Max events per worker loop |
| `WORKER_CONCURRENCY` | 8 | Max concurrent async tasks per worker |
| `BUFFER_FLUSH_INTERVAL_S` | 3.0 | User buffer flush threshold (seconds) |
| `BUFFER_MAX_SIZE` | 20 | User buffer size flush threshold |
| `BUFFER_MAX_WAIT_S` | 5.0 | Hard max buffer hold time |
| `HOT_USER_EMAILS_PER_MIN` | 10 | Threshold for hot user detection |
| `RATE_GMAIL_PER_USER_PER_SEC` | 2.0 | Per-user Gmail API rate |
| `RATE_GMAIL_GLOBAL_PER_SEC` | 200.0 | Global Gmail API rate |
| `BACKPRESSURE_LAG_THRESHOLD` | 50,000 | Start throttling at this lag |
| `BACKPRESSURE_LAG_CRITICAL` | 200,000 | Aggressive throttle threshold |
| `DEDUP_BLOOM_CAPACITY` | 10,000,000 | Bloom filter entries per bucket |
| `DEDUP_BLOOM_ERROR_RATE` | 0.001 | Bloom filter false positive rate |
| `IDEMPOTENCY_CACHE_SIZE` | 500,000 | LRU cache max entries |
| `IDEMPOTENCY_TTL_S` | 3600 | Idempotency key TTL (1h) |
| `DLQ_MAX_RETRIES` | 3 | Retries before DLQ |
| `DB_WRITE_BATCH_SIZE` | 200 | Rows per bulk INSERT |
| `WARMUP_STAGES` | [10%, 30%, 60%, 100%] | Batch size warmup progression |
| `WARMUP_STAGE_SECS` | 30 | Seconds between warmup stages |
| `METRICS_PORT` | 9090 | Prometheus scrape port |

---

## 15. Environment Variables (`.env`)

```env
# Core infrastructure
DATABASE_URL=postgresql://...
REDIS_URL=rediss://default:{token}@relevant-filly-93376.upstash.io:6379

# Gmail OAuth (email connection flow)
GOOGLE_CLIENT_ID_EMAIL=...
GOOGLE_CLIENT_SECRET_EMAIL=...
GOOGLE_REDIRECT_URI_EMAIL=http://localhost:3000/oauth/callback

# Gmail Pub/Sub
GMAIL_PUBSUB_TOPIC=projects/{project}/topics/gmail-notifications

# Outlook OAuth
MICROSOFT_CLIENT_ID_EMAIL=...
MICROSOFT_CLIENT_SECRET_EMAIL=...
MICROSOFT_TENANT_ID_EMAIL=common
MICROSOFT_REDIRECT_URI_EMAIL=http://localhost:3000/oauth/callback

# Encryption
ENCRYPTION_KEY={base64-encoded 32-byte key}

# JWT
JWT_SECRET_KEY=...
JWT_ALGORITHM=HS256

# Public URL (for Outlook webhook registration)
EMAIL_SERVICE_PUBLIC_URL=https://your-ngrok-url.ngrok-free.app

# Automation service
AUTOMATION_SERVICE_URL=http://localhost:8009
```

---

## 16. Performance Targets

| Metric | Target | How achieved |
|--------|--------|--------------|
| Webhook response | < 5ms | XADD only, no API/DB calls |
| Message processing | < 200ms | Async pipeline, bulk DB writes |
| Gmail API reduction | 70-80% | User aggregation buffer |
| Concurrent users | 1M+ | Redis Streams + horizontal worker scaling |
| Memory per worker | < 100MB | Bloom filter 34MB, LRU 50MB, rest minimal |
| DB connections | Bounded | SQLAlchemy pool (15 + 10 overflow) |
| Redis connections | Bounded | Single shared pool (20 max) |

---

## 17. Failure Handling

| Failure | Behavior |
|---------|----------|
| Redis unavailable | Webhook fails open (returns error but doesn't crash). Workers retry with 5s backoff. |
| DB unavailable | Storage worker retries. Events stay in `store_ready` stream (XAUTOCLAIM after 60s). |
| Gmail 429 | Fetch worker backs off 10s, releases envelope for retry. Rate limiter prevents future spikes. |
| Gmail 401 | Logged as error. Token refresh attempted on next event. |
| Gmail historyId expired (404) | Logged as warning. History recovery worker handles gap on next 6-day run. |
| Worker crash | XAUTOCLAIM reclaims unACKed messages after 60s idle. |
| Batch processing error | Failed records retried up to 3 times, then moved to `email_dlq`. |
| Startup after downtime | History recovery runs once on startup, catches all missed messages via History API. |

---

## 18. File Structure

```
emailservice/
├── main.py                    # FastAPI app, lifespan, startup tasks
├── config.py                  # All tuning constants
├── run_worker.py              # Worker process entry point
├── stream_client.py           # Redis Streams producer + consumer
├── kafka_client.py            # Compatibility shim → stream_client
├── encryption.py              # AES-256-GCM encrypt/decrypt
├── schemas.py                 # Pydantic models for /connect endpoint
├── adapters.py                # Gmail / Outlook / SMTP OAuth adapters
├── connection_service.py      # EmailConnectionService (upsert logic)
├── dependencies.py            # JWT auth dependency
├── token_cache.py             # 3-layer account snapshot + token cache
├── dedup.py                   # Time-bucketed Bloom filter
├── idempotency.py             # LRU idempotency cache
├── rate_limiter.py            # Token bucket rate limiter
├── user_buffer.py             # User aggregation buffer + priority engine
├── email_filter.py            # Spam / OTP / promo filter
├── metrics.py                 # Prometheus metrics (no-op if not installed)
├── api/
│   ├── webhooks.py            # Gmail + Outlook webhook handlers
│   ├── connect.py             # POST /email/connect
│   ├── inbox.py               # GET /email/inbox/threads
│   ├── send_reply.py          # POST /email/send-reply
│   └── accounts.py            # GET/DELETE /email/accounts
├── models/
│   ├── email_account.py       # email_accounts table (unchanged schema)
│   ├── messages.py            # es_messages table (append-only)
│   └── conversations.py       # es_conversations table
└── workers/
    ├── base_worker.py         # BaseWorker (backpressure, DLQ, warmup)
    ├── gmail_fetch_worker.py  # Gmail History API fetch
    ├── outlook_fetch_worker.py # Graph API fetch
    ├── smtp_fetch_worker.py   # IMAP fetch + SmtpPoller
    ├── filter_dedup_worker.py # Filter + dedup + direction detection
    ├── storage_worker.py      # Bulk DB writes + ai_events publish
    ├── ai_handoff_worker.py   # AI/automation handoff
    ├── history_recovery_worker.py # 6-day gap recovery
    └── watch_manager.py       # Gmail watch + Outlook subscription mgmt
```
