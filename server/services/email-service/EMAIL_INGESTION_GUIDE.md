# Email Ingestion System — Complete Guide

## 1. Pub/Sub Webhook Endpoint

Paste this URL in **Google Cloud Console → Pub/Sub → Subscriptions → your subscription → Edit → Endpoint URL**:

```
http://<YOUR_SERVER_IP_OR_DOMAIN>:8004/webhooks/gmail
```

**Local development with ngrok:**
```bash
ngrok http 8004
# Copy the https URL, e.g. https://abc123.ngrok.io
# Paste: https://abc123.ngrok.io/webhooks/gmail
```

**Production:**
```
https://api.yourdomain.com/webhooks/gmail
```

> The subscription must be a **Push** subscription, not Pull.  
> Delivery type: **Push**  
> Endpoint URL: the URL above  
> Enable authentication: optional (JWT validation is stubbed — enable in production)

---

## 2. Running the Celery Worker

Open a **separate terminal** (keep the FastAPI server running in another):

```bat
cd server\services\email-service
start-celery-worker.bat
```

Or manually:
```bat
cd server\services\email-service
set PYTHONPATH=%cd%;%cd%\..\..
celery -A email_queue.config.celery_config:email_celery_app worker --loglevel=info --pool=solo --queues=email_events_queue,email_retry_queue,email_dlq --concurrency=4 -n email_worker@%COMPUTERNAME%
```

**Verify worker is connected:**
```bat
celery -A email_queue.config.celery_config:email_celery_app inspect ping
```

---

## 3. Full Email Ingestion Workflow

```
Gmail sends email
      │
      ▼
Google Cloud Pub/Sub
(topic: projects/gmail-integration-484614/topics/gmail-notifications)
      │
      │  HTTP POST (push notification)
      ▼
┌─────────────────────────────────────────────────────┐
│  POST /webhooks/gmail                               │
│  email-service  (port 8004)                         │
│                                                     │
│  GmailReceiver.receive_notification()               │
│  ├─ Parse Pub/Sub envelope                          │
│  ├─ Extract messageId, emailAddress, historyId      │
│  └─ Dedup check on Pub/Sub messageId (Redis)        │
└─────────────────────────────────────────────────────┘
      │  (not duplicate)
      ▼
┌─────────────────────────────────────────────────────┐
│  EmailNormalizer.normalize("gmail", raw_event)      │
│                                                     │
│  AdapterFactory → GmailEventAdapter.parse()         │
│  ├─ GET /gmail/v1/users/me/history?startHistoryId=X │
│  │   (fetches what changed since last notification) │
│  ├─ GET /gmail/v1/users/me/messages/{id}?format=full│
│  │   (fetches full email: headers + body)           │
│  ├─ Extracts: subject, from, to, cc, body text/html │
│  └─ Returns structured intermediate dict            │
│                                                     │
│  AccountMapper  → resolves email_account_id         │
│  UserMapper     → resolves user_id                  │
│  MetadataEnricher → detects direction, normalizes   │
│                     timestamps to UTC               │
│                                                     │
│  Returns: NormalizedEmailEvent (Pydantic model)     │
└─────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────┐
│  EmailFilter.should_filter(subject, from_email)     │
│  ├─ OTP / verification code?  → DROP                │
│  ├─ no-reply / donotreply?    → DROP                │
│  └─ Promotional keywords?     → DROP                │
└─────────────────────────────────────────────────────┘
      │  (passes filter)
      ▼
┌─────────────────────────────────────────────────────┐
│  EventDeduplicator.is_duplicate(gmail_msg_{id})     │
│  Redis key: dedup:event:gmail_msg_{message_id}      │
│  TTL: 24 hours                                      │
└─────────────────────────────────────────────────────┘
      │  (not duplicate)
      ▼
┌─────────────────────────────────────────────────────┐
│  EventProducer.produce(normalized_event)            │
│                                                     │
│  EventRouter → calculates priority (1–10)           │
│  ├─ Urgent keywords in subject → +3                 │
│  ├─ VIP sender domain         → +2                  │
│  ├─ Incoming direction        → +1                  │
│  └─ Has attachments           → +1                  │
│                                                     │
│  process_email_event.apply_async(                   │
│      queue="email_events_queue",                    │
│      priority=N,                                    │
│      routing_key="email.gmail.incoming"             │
│  )                                                  │
│                                                     │
│  Redis queue: email_events_queue                    │
└─────────────────────────────────────────────────────┘
      │
      │  (Celery picks up task)
      ▼
┌─────────────────────────────────────────────────────┐
│  Celery Worker  (start-celery-worker.bat)           │
│                                                     │
│  queue.tasks.email_tasks.process_email_event()      │
│  └─ EventProcessor.process_event(payload)           │
│      │                                              │
│      ├─ Validate required fields                    │
│      ├─ Dedup check on message_id (DB)              │
│      ├─ Fetch existing conversation by thread_id    │
│      │                                              │
│      ├─ JSONConversationManager                     │
│      │   ├─ create_message_object()                 │
│      │   ├─ update_messages()                       │
│      │   │   ├─ Append new message                  │
│      │   │   ├─ Sort by timestamp ASC               │
│      │   │   └─ Apply 24h sliding window filter     │
│      │   └─ Returns: last_24h_messages[]            │
│      │                                              │
│      └─ EmailConversationRepository.upsert()        │
└─────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────┐
│  PostgreSQL — email_conversations table             │
│                                                     │
│  INSERT or UPDATE (by user_id + thread_id)          │
│  ├─ thread_id       (Gmail threadId)                │
│  ├─ message_id      (latest message)                │
│  ├─ from_email                                      │
│  ├─ subject                                         │
│  ├─ last_24h_messages  (JSONB array, 24h window)    │
│  ├─ last_message_at                                 │
│  ├─ is_read = false                                 │
│  └─ conversation_status = "active"                  │
└─────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────┐
│  WebSocket Notification (future)                    │
│  Payload sent to notification-service:              │
│  { type: "new_email", user_id, thread_id,           │
│    subject, content_preview, timestamp }            │
└─────────────────────────────────────────────────────┘
```

---

## 4. Retry & Dead Letter Queue Flow

```
Task fails
    │
    ├─ Retry 1 → after 10s
    ├─ Retry 2 → after 30s
    ├─ Retry 3 → after 60s  (BaseEmailTask.max_retries = 3)
    │
    └─ All retries exhausted
           │
           ▼
    handle_dlq_event task
    ├─ Logs error with full traceback
    └─ Stores in Redis: email:dlq:events (last 1000)

View DLQ:  GET http://localhost:8004/queue/dlq
```

---

## 5. Subscription Auto-Renewal

Gmail watch subscriptions expire every **7 days**. The system auto-renews them:

```
SubscriptionScheduler (background task, runs every 1 hour)
    │
    ├─ Query DB: subscriptions expiring within 24h
    ├─ For each: GmailSubscriber.renew(account)
    │   └─ POST /gmail/v1/users/me/watch  (new watch)
    └─ Update DB + Redis cache
```

Manual trigger:
```
POST http://localhost:8004/subscriptions/renew/check
```

---

## 6. Outlook Provider Flow

Same pipeline, different entry point:

```
Microsoft Graph → POST /webhooks/outlook
OutlookReceiver → OutlookEventAdapter
    └─ GET /v1.0/me/messages/{id}
```

Outlook webhook validation (one-time, on subscription creation):
- Microsoft sends a GET with `?validationToken=...`
- The endpoint returns the token as plain text
- This is handled automatically in `api/webhooks.py`

---

## 7. SMTP Provider Flow

SMTP has no push — it uses polling:

```
SMTPPoller (background task, runs every 60s)
    │
    ├─ For each SMTP account: IMAP IDLE / fetch unseen
    ├─ SMTPEventAdapter → parse raw email
    └─ Same pipeline from filter → queue → worker → DB
```

---

## 8. Key API Endpoints

| Method | URL | Purpose |
|--------|-----|---------|
| POST | `/webhooks/gmail` | Gmail Pub/Sub push endpoint |
| POST | `/webhooks/outlook` | Outlook Graph push endpoint |
| GET | `/health` | Service health (DB + Redis) |
| GET | `/monitoring/health` | Background tasks health |
| GET | `/monitoring/subscriptions/summary` | Subscription stats |
| POST | `/subscriptions/sync` | Force sync all subscriptions |
| POST | `/subscriptions/renew/check` | Force renewal check |
| GET | `/queue/health` | Queue + worker health |
| GET | `/queue/stats` | Queue lengths + processing rate |
| GET | `/queue/dlq` | View failed events |
| POST | `/email/connect` | Connect Gmail/Outlook/SMTP account |
| GET | `/email/accounts` | List connected accounts |

---

## 9. Environment Variables Checklist

Required in `server/.env`:

```env
# Database
DATABASE_URL=postgresql://...

# Redis (broker + cache)
REDIS_URL=redis://...
CELERY_BROKER_URL=redis://...
CELERY_RESULT_BACKEND=redis://...

# Gmail Pub/Sub
GMAIL_PUBSUB_TOPIC=projects/<PROJECT_ID>/topics/<TOPIC_NAME>
GMAIL_PUBSUB_SUBSCRIPTION=projects/<PROJECT_ID>/subscriptions/<SUB_NAME>

# Gmail OAuth (email connection)
GOOGLE_CLIENT_ID_EMAIL=...
GOOGLE_CLIENT_SECRET_EMAIL=...
GOOGLE_REDIRECT_URI_EMAIL=http://localhost:3000/oauth/callback

# Encryption (AES-256, base64-encoded 32-byte key)
ENCRYPTION_KEY=...

# JWT
JWT_SECRET_KEY=...
```

---

## 10. Startup Order

```
1. PostgreSQL  (must be running)
2. Redis       (must be running)
3. email-service FastAPI:   run.bat          (port 8004)
4. Celery worker:           start-celery-worker.bat
```

Both 3 and 4 must be running simultaneously for the full pipeline to work.
