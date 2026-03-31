# Mail Automation System — Server-Side Architecture Documentation

## Executive Summary

Enterprise-grade microservices platform built with **Python FastAPI** for scalable email automation and AI-powered inbox management. The system features 12 independent microservices, a fully implemented real-time email ingestion engine (Gmail Pub/Sub + Outlook Graph), gap recovery guarantees, and an AI-first conversation storage model.

**Architecture**: Microservices + Event-Driven + Async-First  
**Language**: Python 3.11+  
**Framework**: FastAPI 0.109.0  
**Deployment**: Docker + Docker Compose (local: direct Python)

---

## System Architecture Overview

```
Client (Next.js :3000)
        │
        ▼
Gateway Service (:8000)   ← API routing, rate limiting, circuit breaker
        │
        ├── Auth Service (:8001)        JWT + OAuth 2.0 + Celery worker
        ├── User Service (:8002)        Profiles, settings
        ├── Business Service (:8003)    Business context, knowledge base
        ├── Email Service (:8004)       Gmail/Outlook ingestion engine  ← CORE
        ├── Inbox Service (:8005)       (stub — inbox logic in email-service)
        ├── Campaign Service (:8006)    Email campaigns
        ├── Leads Service (:8007)       Lead management, CSV import
        ├── Analytics Service (:8008)   Reporting, metrics
        ├── Automation Service (:8009)  Workflow automation, AI
        ├── Research Service (:8010)    Data research, enrichment
        └── Notification Service (:8011) Real-time notifications

Shared Infrastructure (all services import from server/shared/)
        ├── PostgreSQL (Amazon RDS)     Primary relational store
        ├── MongoDB Atlas               Document store
        ├── Redis Cloud                 Cache + Celery broker
        └── Qdrant (:6333)             Vector database (embeddings)
```

---

## Project Structure

```
server/
├── shared/                          # Shared infrastructure — ALL services use this
│   ├── config/settings.py           # Pydantic settings, loads .env
│   ├── database/
│   │   ├── postgres.py              # Async PostgreSQL pool (asyncpg)
│   │   └── mongodb.py               # Async MongoDB client (Motor)
│   ├── cache/redis_client.py        # Async Redis with get_redis() helper
│   ├── celery/celery_app.py         # Shared Celery app (auth + user workers)
│   ├── logger/logging_config.py     # Structured logging + request ID
│   ├── utils/http_client.py         # Inter-service HTTP client
│   └── vector_db/qdrant_client.py   # Qdrant vector DB client
│
├── services/
│   ├── gateway-service/             # Port 8000 — API gateway
│   ├── auth-service/                # Port 8001 — JWT + OAuth
│   ├── user-service/                # Port 8002 — User profiles
│   ├── business-service/            # Port 8003 — Business context
│   ├── email-service/               # Port 8004 — Email ingestion engine
│   │   ├── adapter/                 # Provider-specific event parsers
│   │   │   └── providers/
│   │   │       ├── gmail_adapter.py     Gmail History API + token refresh
│   │   │       ├── outlook_adapter.py   Graph API message fetch
│   │   │       └── smtp_adapter.py      SMTP/IMAP parsing
│   │   ├── adapters/                # OAuth connection adapters (connect flow)
│   │   ├── api/
│   │   │   ├── connect.py           POST /email/connect
│   │   │   ├── accounts.py          CRUD for email accounts
│   │   │   ├── webhooks.py          POST /webhooks/gmail + /outlook
│   │   │   ├── subscriptions.py     Subscription management endpoints
│   │   │   ├── inbox.py             GET /email/inbox/threads (polling)
│   │   │   ├── monitoring.py        Health + stats
│   │   │   └── queue.py             Queue stats + DLQ viewer
│   │   ├── database/repository.py   EmailConversation CRUD
│   │   ├── email_queue/             Celery queue (renamed from 'queue')
│   │   │   ├── config/celery_config.py  Celery app + Beat schedule
│   │   │   ├── tasks/
│   │   │   │   ├── email_tasks.py       process/retry/dlq tasks
│   │   │   │   ├── scheduled_tasks.py   subscription_refresh, history_sync, cleanup
│   │   │   │   └── base_task.py         BaseEmailTask with DLQ on failure
│   │   │   ├── producer/event_producer.py  Push to queue
│   │   │   └── monitoring/queue_monitor.py Queue stats
│   │   ├── models/
│   │   │   ├── email_account.py         EmailAccount ORM
│   │   │   ├── email_conversation.py    EmailConversation ORM (AI-first)
│   │   │   └── email_provider_subscription.py  Watch/subscription tracking
│   │   ├── normalizer/
│   │   │   ├── normalizer.py            EmailNormalizer orchestrator
│   │   │   ├── event_schema.py          NormalizedEmailEvent Pydantic model
│   │   │   └── enrichers/               user_mapper, account_mapper, metadata
│   │   ├── provider/
│   │   │   ├── deduplicator/            Redis-based event deduplication
│   │   │   ├── filters/email_filter.py  Spam/OTP/no-reply filter
│   │   │   ├── manager/subscription_manager.py  Watch lifecycle
│   │   │   ├── receivers/               gmail_receiver, outlook_receiver, smtp_receiver
│   │   │   ├── scheduler/               subscription_scheduler, smtp_poller, background_tasks
│   │   │   └── subscribers/             gmail_subscriber, outlook_subscriber, smtp_subscriber
│   │   ├── recovery/
│   │   │   ├── history_sync.py          Gmail History API gap recovery
│   │   │   └── watch_cleanup.py         Stop unknown/stale Gmail watches
│   │   ├── services/email_connection_service.py  Connect + save account
│   │   ├── utils/encryption.py          AES-256-GCM token encryption
│   │   └── worker/
│   │       ├── processor.py             EventProcessor (validate→store)
│   │       ├── json_manager.py          24h sliding window + quote stripping
│   │       └── consumer.py              Legacy consumer (superseded by email_tasks)
│   ├── inbox-service/               # Port 8005 — stub
│   ├── campaign-service/            # Port 8006
│   ├── leads-service/               # Port 8007
│   ├── analytics-service/           # Port 8008
│   ├── automation-service/          # Port 8009
│   ├── research-service/            # Port 8010
│   └── notification-service/        # Port 8011
│
├── .env                             # Single config file for ALL services
├── docker-compose.yml               # 12 services + Qdrant + auth-celery-worker
└── SERVER_SIDE_ARCHITECTURE_DOCUMENTATION.md
```

---

## Shared Infrastructure Layer

### 1. Configuration (`shared/config/settings.py`)

Single source of truth loaded from `server/.env`.

Key additions vs original:
- `GMAIL_PUBSUB_TOPIC` / `GMAIL_PUBSUB_SUBSCRIPTION` — Google Cloud Pub/Sub
- `EMAIL_SERVICE_PUBLIC_URL` — public ngrok/domain URL for Outlook webhook validation
- `GOOGLE_CLIENT_ID_EMAIL` / `GOOGLE_CLIENT_SECRET_EMAIL` — separate OAuth credentials for email connection flow
- `CORS_ORIGINS` and `CELERY_ACCEPT_CONTENT` parse both JSON array and comma-separated formats

```python
from shared.config import get_config
config = get_config()
```

### 2. Database (`shared/database/`)

**PostgreSQL** — async via SQLAlchemy + asyncpg. Pool: 5 connections, 3 overflow (tuned for Windows dev). AWS RDS SSL enforced. Engine globals reset per Celery task to avoid "event loop closed" errors.

**MongoDB** — async via Motor. Used for document storage.

**Usage**:
```python
async with get_db_session() as session:
    result = await session.execute(query)
    await session.commit()
```

### 3. Cache (`shared/cache/redis_client.py`)

Single shared async Redis client. Pool: 5 connections (free-tier Redis budget).

`get_redis()` is an async function — always `await get_redis()`.

```python
from shared.cache import get_redis
redis = await get_redis()
await redis.setex("key", 3600, "value")
```

### 4. Celery — Two Separate Apps

**Shared Celery** (`shared/celery/celery_app.py`): Used by auth-service and user-service workers.
- Queues: `auth_queue`, `user_queue`
- Tasks: `auth.create_user_embedding`, `user.update_user_embedding`
- Broker pool: 1 connection, retry forever on disconnect

**Email Celery** (`email-service/email_queue/config/celery_config.py`): Dedicated to email-service.
- Queues: `email_events_queue`, `email_retry_queue`, `email_dlq`
- Includes: `email_queue.tasks.email_tasks`, `email_queue.tasks.scheduled_tasks`
- Beat schedule: subscription refresh (1h), history sync (30m), watch cleanup (24h)
- Broker pool: 2 connections, `socket_keepalive: True`, retry forever

### 5. Logger (`shared/logger/`)

Structured logging with request ID context. All verbose pipeline logs are `logger.debug()` — only errors and warnings appear at default `INFO` level.

---

## Email Service — Deep Architecture

The email-service is the most complex service. It implements a complete, fault-tolerant email ingestion engine.

### Email Ingestion Pipeline (Real-Time)

```
Gmail sends email
      │
      ▼
Google Cloud Pub/Sub
(topic: projects/gmail-integration-484614/topics/gmail-notifications)
      │  HTTP POST push notification
      ▼
POST /webhooks/gmail
GmailReceiver.receive_notification()
      │
      ├─ 1. Parse Pub/Sub envelope (messageId, emailAddress, historyId)
      ├─ 2. Dedup on Pub/Sub messageId (Redis, 24h TTL) — stops retry storms
      ├─ 3. Mark processed BEFORE expensive work
      ├─ 4. Normalize:
      │       GmailEventAdapter.parse()
      │         ├─ Look up account by emailAddress in DB
      │         │   └─ Unknown accounts: rate-limited warning (once/hour), return None
      │         ├─ Determine startHistoryId:
      │         │   ├─ Use account.last_history_id (previous cursor) if available
      │         │   └─ Fall back to (new_historyId - 1)
      │         ├─ Refresh access token if expired (auto, saves to DB)
      │         ├─ GET /gmail/v1/users/me/history?startHistoryId=X
      │         │   ├─ 401 → error (re-connect needed)
      │         │   ├─ 404 → historyId expired, fall back to latest inbox message
      │         │   └─ Empty history → return None (no new messages, silent)
      │         ├─ GET /gmail/v1/users/me/messages/{id}?format=full
      │         │   ├─ Skip DRAFT, SPAM, TRASH labels
      │         │   ├─ Only process INBOX or SENT
      │         │   └─ 404 → message deleted before fetch, debug log only
      │         └─ Advance account.last_history_id to new value
      │
      ├─ 5. Filter (EmailFilter): spam keywords, OTP, no-reply patterns
      ├─ 6. Dedup on Gmail message_id (Redis, 24h TTL)
      └─ 7. Push to Celery queue (email_events_queue, priority 1-10)
                │
                ▼
      Celery Worker (start-celery-worker.bat)
      process_email_event task
                │
                ├─ Reset async DB engine (new event loop per task)
                ├─ EventProcessor.process_event()
                │   ├─ Validate required fields
                │   ├─ Dedup by message_id in DB
                │   ├─ Fetch existing conversation by thread_id
                │   ├─ JSONConversationManager.create_message_object()
                │   │   └─ _strip_quoted_reply(): removes "On Mon, 30 Mar, 2026..."
                │   ├─ update_messages(): append + sort + 24h filter
                │   └─ EmailConversationRepository.upsert_conversation()
                │       ├─ UPDATE if thread exists
                │       └─ INSERT if new thread
                └─ Return success (DLQ on 3 retries exhausted)
```

### Gap Recovery System (Zero Data Loss)

Pub/Sub is the fast path. Gmail History API is the safety net.

```
On startup (after 10s delay):
  GmailHistorySync.run_recovery_for_all()
    │
    For each active Gmail account (batches of 50):
      ├─ Skip if no last_history_id stored
      ├─ Skip if last_synced_at < 60s ago
      ├─ GET /gmail/v1/users/me/history?startHistoryId=<last_history_id>
      │   ├─ Handles pagination (nextPageToken)
      │   ├─ Exponential backoff on 429 rate limits
      │   └─ 404 → historyId expired (>7 days), skip
      ├─ For each missed message: normalize → filter → dedup → queue
      └─ Advance last_history_id + update last_synced_at

Also runs every 30 minutes via Celery Beat (history_sync_task).
```

### Subscription Lifecycle

```
Account connected (POST /email/connect)
      │
      └─ asyncio.create_task(_register_watch_subscription(account))
              │
              ▼
      SubscriptionManager.ensure_subscription()
              │
              ├─ GMAIL:   GmailSubscriber.subscribe()
              │             POST /gmail/v1/users/me/watch
              │             → stores historyId as last_history_id
              │             → expires in 6 days (renewed 1 day early)
              │
              ├─ OUTLOOK: OutlookSubscriber.subscribe()
              │             POST /graph.microsoft.com/v1.0/subscriptions
              │             → requires EMAIL_SERVICE_PUBLIC_URL (ngrok in dev)
              │             → expires in 2.5 days
              │
              └─ SMTP:    SMTPSubscriber.subscribe()
                            Registers in Redis for SMTPPoller

Auto-renewal (every 1 hour via Celery Beat — subscription_refresh_task):
  SubscriptionManager.sync_all_subscriptions()
    → renews subscriptions expiring within 24h

Unknown watch cleanup (every 24h via Celery Beat — cleanup_task):
  WatchCleanup.cleanup_all_unknown_watches()
    → stops Gmail watches for addresses not in DB
    → POST /subscriptions/stop-unknown-watch for manual stop
```

### Message Storage Schema

`last_24h_messages` JSONB field stores a clean, AI-ready message array:

```json
[
  {
    "from":            "sender@example.com",
    "to":              ["recipient@example.com"],
    "content":         "Actual message text only — quoted replies stripped",
    "timestamp":       "2026-03-29T13:31:54",
    "direction":       "incoming",
    "has_attachments": false
  }
]
```

Fields intentionally excluded from the JSONB object:
- `message_id` → stored as `EmailConversation.message_id` (dedup key)
- `subject` → stored as `EmailConversation.subject`
- `cc` → not needed for AI context

Quote stripping logic (`_strip_quoted_reply`):
- Finds the LAST `"On <weekday>,"` pattern in the string
- Only cuts if a 4-digit year follows (prevents false positives on "on monday")
- Handles both inline and multi-line Gmail/Outlook quote formats

### Inbox API (Polling — No SSE/WebSocket)

SSE/WebSocket was removed to avoid exhausting the free-tier Redis connection limit. The client polls every 30 seconds.

```
GET  /email/inbox/threads          List all active conversations
GET  /email/inbox/threads/{id}     Get single thread with messages
POST /email/inbox/threads/{id}/read  Mark as read
```

### Key API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/email/connect` | Connect Gmail/Outlook/SMTP account |
| GET | `/email/accounts` | List connected accounts |
| POST | `/webhooks/gmail` | Gmail Pub/Sub push endpoint |
| GET | `/webhooks/gmail` | GET probe (Google validation) |
| POST | `/webhooks/outlook` | Outlook Graph push + validation handshake |
| GET | `/webhooks/outlook` | GET probe (Microsoft validation) |
| POST | `/webhooks/gmail/test` | Simulate Pub/Sub push for testing |
| GET | `/webhooks/debug/account/{email}` | Check if account is in DB |
| GET | `/email/inbox/threads` | List inbox threads (polling) |
| POST | `/subscriptions/sync` | Force sync all watches |
| POST | `/subscriptions/stop-unknown-watch` | Stop stale Gmail watch |
| GET | `/subscriptions/unknown-watches` | List unknown watch addresses |
| GET | `/subscriptions/status` | All subscriptions with status |
| GET | `/queue/health` | Queue + worker health |
| GET | `/queue/dlq` | View failed events |

---

## Gateway Service

Catch-all reverse proxy that forwards every request to the appropriate microservice based on URL prefix.

```python
@app.api_route("/{path:path}", methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"])
async def gateway_router(request: Request):
    return await route_request(request)
```

Features: circuit breaker, rate limiting (60 req/min), request ID propagation, connection pooling.

---

## Auth Service

JWT authentication + OAuth 2.0 (Google + Microsoft).

**Startup**: Creates DB tables, initializes connections.

**Celery Worker** (`start-worker.bat`):
- Queue: `auth_queue`
- Task: `auth.create_user_embedding` — generates Qdrant vector embeddings on user registration
- Pool: solo (Windows-safe), 1 concurrency

**Key flows**:
- Sign up → create user → queue embedding task → return JWT
- Sign in → validate credentials → return JWT + refresh token
- OAuth → exchange code → fetch user info → upsert user → return JWT

---

## User Service

User profile management and settings.

**Celery Worker** (`start-worker.bat`):
- Queue: `user_queue`
- Task: `user.update_user_embedding` — partial vector update when AI context fields change
- Smart: only regenerates affected vector chunks (business_core, audience, tone, etc.)

---

## Database Architecture

### PostgreSQL (Amazon RDS — ap-south-1)

Primary relational store. All services share one instance.

Key tables:
- `users` — auth-service
- `email_accounts` — email-service (with `last_history_id`, `watch_expiry` columns added via migration)
- `email_conversations` — email-service (AI-first, JSONB message history)
- `email_provider_subscriptions` — watch/subscription tracking

**Datetime rule**: All timestamps stored as `TIMESTAMP WITHOUT TIME ZONE` (naive UTC). asyncpg rejects timezone-aware datetimes for naive columns — always use `datetime.utcnow()` not `datetime.now(timezone.utc)` when writing to DB.

### Redis Cloud (ap-south-1)

Free-tier instance with ~30 connection limit. Connection budget:
- FastAPI async pool: 5 connections
- Email Celery worker broker: 3 connections
- Email Celery worker result: 2 connections
- Auth/User Celery workers: 2+1 connections
- Total: ~13 (well within limit)

Redis key namespaces:
```
dedup:event:{key}           Pub/Sub + message dedup (24h TTL)
gmail:unknown:watches       Set of unknown emailAddresses
gmail:unknown:warned:{email} Rate-limit key for unknown watch warnings (1h TTL)
sub:id:{subscription_id}    subscription_id → email_account_id (24h TTL)
sub:account:{account_id}    account_id → "sub_id|user_id" (24h TTL)
email:dlq:events            List of DLQ events (last 1000)
smtp:polling:accounts       Set of SMTP account IDs for polling
```

### Qdrant (Vector DB)

Used by auth-service and user-service for business context embeddings.
- Collection: `business_context`
- Model: `all-MiniLM-L6-v2` (384 dimensions)
- Distance: Cosine

---

## Running Locally

### Startup Order

```
1. PostgreSQL (Amazon RDS — always available)
2. Redis (RedisLabs — always available)
3. Qdrant: start-qdrant.bat
4. Auth Service:    cd services/auth-service && run.bat
5. Auth Worker:     cd services/auth-service && start-worker.bat
6. User Service:    cd services/user-service && run.bat
7. User Worker:     cd services/user-service && start-worker.bat
8. Email Service:   cd services/email-service && run.bat
9. Email Worker:    cd services/email-service && start-celery-worker.bat
10. Email Beat:     cd services/email-service && start-celery-beat.bat
11. Gateway:        cd services/gateway-service && python main.py
```

Or use `start.bat` in email-service to launch FastAPI + worker + beat together.

### PYTHONPATH

Every service requires:
```bat
set PYTHONPATH=%cd%;%cd%\..\..
```
This puts both the service root and `server/` on the path so `from shared.X import Y` works.

### Gmail Pub/Sub (Local Dev)

1. Run ngrok: `ngrok http 8004`
2. Copy the `https://` URL (no port)
3. Set in Google Cloud Console → Pub/Sub → subscription → endpoint URL:
   `https://<subdomain>.ngrok-free.app/webhooks/gmail`
4. The system auto-registers Gmail watches on startup

### Outlook Webhooks (Local Dev)

Set `EMAIL_SERVICE_PUBLIC_URL` in `server/.env` to your ngrok URL:
```env
EMAIL_SERVICE_PUBLIC_URL=https://your-subdomain.ngrok-free.app
```
Microsoft validates the endpoint before creating the subscription.

---

## Security

### Token Encryption

All OAuth tokens stored encrypted with AES-256-GCM:
```python
from utils.encryption import encrypt_token, decrypt_token
stored = encrypt_token(raw_token)   # base64(nonce + ciphertext)
raw    = decrypt_token(stored)
```

### JWT

- Algorithm: HS256
- Access token: 30 days (259,200 minutes)
- Refresh token: 180 days

### CORS

Configured per environment via `CORS_ORIGINS` in `.env`. Supports both JSON array and comma-separated formats.

---

## Docker Deployment

All 12 services + Qdrant + auth-celery-worker defined in `docker-compose.yml`.

```bash
docker-compose up --build          # Start everything
docker-compose up email-service    # Start specific service
docker-compose logs -f email-service
docker-compose down
```

Each service:
- Shares `./shared` volume (read-only)
- Shares `./.env` volume (read-only)
- `PYTHONPATH=/app`
- Network: `mailautomation-network`
- Restart: `unless-stopped`
- Health check: `GET /health` every 30s

---

## Key Design Decisions

**Why `email_queue` not `queue`?** Python's stdlib has a `queue` module. Naming the folder `queue` caused `concurrent.futures` to fail at import time. Renamed to `email_queue`.

**Why no SSE/WebSocket for inbox?** Free-tier Redis has ~30 connection limit. Each SSE connection opens a Redis pubsub connection. With multiple browser tabs this exhausts the pool. Client polls every 30s instead.

**Why reset DB engine per Celery task?** SQLAlchemy's async engine holds connections tied to the event loop. Celery creates a new event loop per task. Resetting `_engine = None` before each task forces a fresh engine on the new loop, preventing "Event loop is closed" errors on retries.

**Why naive UTC datetimes?** PostgreSQL columns are `TIMESTAMP WITHOUT TIME ZONE`. asyncpg rejects timezone-aware datetimes for these columns. All timestamps use `datetime.utcnow()` and strip tzinfo before DB writes.

**Why two-layer dedup?** Pub/Sub can deliver the same message multiple times. Layer 1 (Pub/Sub messageId) stops retry storms before any expensive API calls. Layer 2 (Gmail message_id) catches duplicates that slip through after normalization.

**Why `last_history_id` on EmailAccount?** Gmail Pub/Sub sends the NEW historyId (current watermark), not the previous one. To fetch what changed, we need `startHistoryId = previous_value`. Storing it on the account enables both correct real-time processing and gap recovery.
