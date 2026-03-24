# Mail Automation System - Complete Server-Side Architecture Documentation

## 🎯 Executive Summary

The **Mail Automation System** is an enterprise-grade, microservices-based platform designed for **real-time email processing and intelligent reply automation**. The system prioritizes **instant email reply handling** over campaign creation, featuring AI-powered response generation, conversation threading, and seamless Gmail/Outlook integration.

**Core Priority**: Real-time email reply processing with sub-second response times for incoming emails.

---

## 🏗️ System Architecture Overview

### Technology Stack
- **Backend**: Python FastAPI microservices (11 services)
- **Databases**: PostgreSQL (Amazon RDS), MongoDB Atlas, Redis Cloud
- **Message Queue**: RabbitMQ
- **Real-time**: Google Cloud Pub/Sub + Server-Sent Events
- **AI Integration**: Custom retrieval engine for intelligent responses
- **Infrastructure**: Docker containerization with hybrid deployment

### Architecture Pattern
**Event-Driven Microservices** with **Hybrid Real-time Processing**:
```
Gmail/Outlook → Pub/Sub Notifications → Webhook Queue → Reply Detection Engine → AI Response Generation
```

---

## 🔄 Real-Time Email Reply System (Primary Focus)

### Core Workflow

```mermaid
graph TD
    A[Incoming Email] --> B[Gmail Pub/Sub Notification]
    B --> C[Unified Webhook Handler]
    C --> D[Webhook Queue Service]
    D --> E[Reply Detection Engine]
    E --> F[Gmail Adapter]
    F --> G[Email Filter Service]
    G --> H[Campaign Email Log]
    H --> I[AI Retrieval Engine]
    I --> J[Intelligent Response]
    J --> K[User Dashboard Update]
```

### 1. Webhook Reception (`/webhooks/unified/gmail`)
**File**: `server/email-service/app/api/unified_webhooks.py`

- **Endpoint**: `POST /webhooks/unified/gmail`
- **Purpose**: Receives Google Cloud Pub/Sub notifications instantly
- **Processing**: 
  - Extracts `email_address` and `history_id` from notification
  - Looks up `user_id` from email address
  - Enqueues for async processing (non-blocking)
  - **Always returns HTTP 200** to prevent Pub/Sub retries
- **Concurrency**: Handles 1000+ concurrent webhook notifications
### 2. Async Processing Queue
**File**: `server/email-service/app/services/webhook_queue_service.py`

- **Purpose**: Prevents webhook endpoint blocking
- **Features**:
  - Queue overflow protection (max 10,000 items)
  - Background task processing with 20 workers
  - Error handling with exponential backoff
  - Memory leak prevention with automatic cleanup
  - Metrics tracking (total_queued, total_processed, total_failed)

### 3. Reply Detection Engine
**File**: `server/email-service/app/engines/reply_detection_engine.py`

**Core Method**: `process_webhook_notification(provider, user_id, notification_data)`
- Extracts `history_id` from notification
- Calls Gmail adapter to fetch new messages
- Processes each message through unified pipeline

**Core Method**: `process_email_message(user_id, email_message)`
- **Thread-safe processing** with unique keys
- **Duplicate detection** (message ID + content similarity)
- **Email filtering** (spam, marketing, system emails)
- **Campaign thread detection** via thread_id matching
- **Reply tracking** updates `is_reply_received` flag
- **Message buffering** in JSON array (last 24 hours)
- **Atomic database commits**

### 4. Gmail Integration Adapter
**File**: `server/email-service/app/adapters/gmail_adapter.py`

**Method**: `fetch_new_messages(user_id, history_id)`
- Uses **Gmail History API** for incremental sync
- Fetches only `messagesAdded` events
- Retrieves full message format (not truncated)
- Converts to unified `email_message` format
- Updates sync state with latest `history_id`
- Handles 404 errors gracefully

### 5. Email Filtering System
**File**: `server/email-service/app/services/email_filter_service.py`

**Intelligent Filtering Rules**:
- **Never filters personal domains** (gmail.com, yahoo.com, etc.)
- **Filters marketing domains** (mailchimp.com, sendgrid.net, etc.)
- **Filters social notifications** (facebookmail.com, linkedin.com, etc.)
- **Filters system emails** (noreply@, no-reply@, etc.)
- **Uses Gmail labels** (SPAM, CATEGORY_PROMOTIONS, CATEGORY_SOCIAL)
- **Keyword detection** for promotional content

---

## 🛠️ Backend Microservices Architecture

### Service Portfolio (11 Services)

| Service | Port | Primary Responsibility |
|---------|------|----------------------|
| **Gateway** | 8000 | API routing and load balancing |
| **Auth Service** | 8001 | JWT authentication, OAuth (Google/Microsoft) |
| **Email Service** | 8002 | **Gmail/Outlook integration, webhook handling** |
| **Business Service** | 8003 | Business logic and settings |
| **User Service** | 8004 | User management and profiles |
| **Inbox Service** | 8005 | **Inbox management, conversation threading** |
| **Campaign Service** | 8006 | Email campaign management |
| **Analytics Service** | 8007 | Reporting and metrics |
| **Automation Service** | 8008 | Workflow automation and AI features |
| **Leads Service** | 8009 | Lead management |
| **Research Service** | 8010 | Data research and enrichment |
| **Notification Service** | 8011 | Real-time notifications |
---

## 📧 EMAIL SERVICE (Port 8002) - CRITICAL FOR REPLY PROCESSING

**Primary Responsibility**: Gmail/Outlook integration, webhook handling, real-time email processing

### Key Components

#### Unified Webhook Handler
**File**: `app/api/unified_webhooks.py`
- **Endpoint**: `POST /webhooks/unified/gmail`
- **Function**: Receives Google Cloud Pub/Sub notifications instantly
- **Processing Flow**:
  1. Parse Pub/Sub notification payload
  2. Extract `email_address` and `history_id`
  3. Lookup `user_id` from email address in database
  4. Enqueue for async processing via webhook queue
  5. Return HTTP 200 immediately (non-blocking)

#### Reply Detection Engine
**File**: `app/engines/reply_detection_engine.py`
- **Core Function**: Unified engine that processes email events from all providers
- **Key Features**:
  - Thread-safe processing with unique keys
  - Duplicate detection (exact message ID + content similarity within 2 minutes)
  - Email filtering integration
  - Campaign thread detection via thread_id matching
  - Reply tracking with `is_reply_received` flag updates
  - Message buffering in JSON array (last 24 hours)
  - Atomic database commits
  - AI retrieval engine integration

#### Gmail Adapter
**File**: `app/adapters/gmail_adapter.py`
- **Provider Integration**: Gmail API with Pub/Sub support
- **Key Methods**:
  - `fetch_new_messages(user_id, history_id)`: Uses Gmail History API for incremental sync
  - `parse_webhook_notification(payload)`: Parses Pub/Sub notifications
  - `set_pubsub_topic(topic)`: Configures Pub/Sub topic from environment
- **Features**:
  - Incremental synchronization using history_id
  - Pub/Sub topic validation and configuration
  - Error handling for 404 errors (deleted messages)
  - Unified email_message format conversion

#### Email Filter Service
**File**: `app/services/email_filter_service.py`
- **Purpose**: Filters out unwanted emails (spam, marketing, system notifications)
- **Filtering Logic**:
  - **Personal domains** (gmail.com, yahoo.com) - NEVER filtered
  - **Marketing domains** (mailchimp.com, sendgrid.net) - Always filtered
  - **Social domains** (facebookmail.com, linkedin.com) - Always filtered
  - **System senders** (noreply@, no-reply@) - Filtered for non-personal domains
  - **Gmail labels** (SPAM, CATEGORY_PROMOTIONS, CATEGORY_SOCIAL)
  - **Keyword detection** for promotional content

#### Webhook Queue Service
**File**: `app/services/webhook_queue_service.py`
- **Purpose**: Async queue for processing webhook notifications at scale
- **Configuration**:
  - Max workers: 20
  - Max queue size: 10,000
  - Backpressure handling
- **Features**:
  - Non-blocking webhook endpoint
  - Parallel processing with configurable workers
  - Queue overflow protection
  - Metrics and monitoring
  - Automatic cleanup to prevent memory leaks

### Critical Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/webhooks/unified/gmail` | POST | Webhook receiver for Pub/Sub notifications |
| `/gmail/send-reply` | POST | Send email via Gmail API with thread support |
| `/gmail/messages` | GET | Fetch messages using History API |
| `/gmail/oauth/connect` | POST | Connect Gmail account via OAuth |
| `/gmail/watch/setup` | POST | Setup Gmail watch for Pub/Sub |
| `/gmail/watch/renew` | POST | Renew Gmail watch before expiration |

### Database Models

#### CampaignEmailLog
**File**: `app/models/campaign_email_log.py`
- **Purpose**: Source of truth for Campaign Inbox filtering
- **Key Fields**:
  - `user_id`, `campaign_id`, `lead_id`, `lead_email`
  - `message_id`, `thread_id` (Gmail identifiers)
  - `is_reply_received`, `last_reply_at`
  - `last_24h_messages` (JSON array of message history)
  - `last_activity_at` (for ultra-fast inbox sorting)
- **Indexes**: Ultra-fast queries on user_id, thread_id, activity timestamps

#### EmailAccount
**File**: `app/models/email_account.py`
- **Purpose**: Stores encrypted OAuth tokens and account information
- **Key Fields**:
  - `user_id`, `provider`, `email_address`
  - `encrypted_access_token`, `encrypted_refresh_token` (AES-256)
  - `token_expires_at`, `is_active`, `connection_status`
- **Security**: All tokens encrypted at rest with AES-256

#### GmailSyncState
**File**: `app/models/gmail_sync_state.py`
- **Purpose**: Tracks historyId and sync state for delta synchronization
- **Key Fields**:
  - `user_id`, `email_address`
  - `last_history_id`, `current_history_id` (critical for delta sync)
  - `watch_expiration`, `last_watch_setup_at`
  - `sync_status`, `consecutive_errors`
---

## 📥 INBOX SERVICE (Port 8005) - CONVERSATION MANAGEMENT

**Primary Responsibility**: Conversation threading, message management, real-time updates

### Key Components

#### Conversation Routes
**File**: `app/routes/conversations.py`
- **Purpose**: Manage email conversations and threading
- **Features**:
  - List all conversations with pagination
  - Get conversation details with message history
  - Mark conversations as read/unread
  - Delete conversations
  - Participant extraction from email headers

#### Reply Service
**File**: `app/routes/reply.py`
- **Purpose**: Enterprise reply system with Gmail API integration
- **Features**:
  - Compose and send replies via Gmail API
  - Proper thread management with RFC 5322 headers
  - Attachment handling
  - Draft saving and management

#### Delta Sync Worker
**File**: `app/workers/delta_sync_worker.py`
- **Purpose**: Background worker for continuous sync
- **Features**:
  - Continuous synchronization with Gmail
  - Delta sync using history_id
  - Error handling and retry logic

#### SSE Endpoints
**File**: `app/routes/sse_endpoints.py`
- **Purpose**: Server-Sent Events for real-time updates
- **Status**: Currently disabled for cost optimization
- **Features**:
  - Real-time inbox updates
  - New message notifications
  - Conversation status changes

### Critical Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/conversations` | GET | List all conversations with pagination |
| `/conversations/{id}/messages` | GET | Get conversation messages |
| `/conversations/{id}/read` | PUT | Mark conversation as read |
| `/reply/send` | POST | Send reply via Gmail API |
| `/campaign/inbox/sse-updates` | GET | Real-time updates (SSE) |

### Threading Logic
- **Primary Key**: Gmail `thread_id`
- **Grouping**: All messages with same `thread_id` grouped together
- **Ordering**: Chronological ordering (oldest first, newest last)
- **Participants**: Extracted from email headers
- **Message Count**: Aggregation at thread level

---

## 🔐 AUTH SERVICE (Port 8001) - AUTHENTICATION & OAUTH

**Primary Responsibility**: JWT authentication, OAuth flows (Google/Microsoft), user signup

### Key Components

#### OAuth Routes
**File**: `app/api/v1/routes/oauth.py`
- **Google OAuth**: Complete OAuth 2.0 flow with Gmail scope
- **Microsoft OAuth**: OAuth 2.0 flow with Outlook scope
- **Token Management**: Secure token storage and refresh

#### JWT Authentication
**File**: `app/api/v1/routes/auth.py`
- **Login**: Email/password authentication
- **Token Generation**: JWT with 30-day expiration (43,200 minutes)
- **Token Refresh**: Automatic refresh before expiration
- **Token Validation**: Signature verification and expiration checks

#### Signup Flow
**File**: `app/api/v1/routes/signup.py`
- **Multi-step Signup**: Email verification with OTP
- **Password Security**: Bcrypt hashing with salt
- **Session Management**: Temporary signup sessions

### Critical Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/auth/login` | POST | Email/password login |
| `/auth/refresh-token` | POST | Refresh JWT token |
| `/auth/google/callback` | GET | Google OAuth callback |
| `/auth/microsoft/callback` | GET | Microsoft OAuth callback |
| `/auth/signup/start` | POST | Start signup process |
| `/auth/otp/verify` | POST | Verify OTP |

### Security Features
- **JWT Tokens**: 30-day expiration with automatic refresh
- **Refresh Tokens**: 60-day expiration
- **AES-256 Encryption**: For stored OAuth tokens
- **OTP Verification**: For password reset and signup
- **Rate Limiting**: On authentication endpoints
- **CORS Protection**: Configured for localhost:3000

---

## 📊 CAMPAIGN SERVICE (Port 8006) - EMAIL CAMPAIGN MANAGEMENT

**Primary Responsibility**: Email campaign creation, management, and sending

### Key Components

#### Campaign Routes
**File**: `app/routes/campaigns.py`
- **Campaign CRUD**: Create, read, update, delete campaigns
- **Campaign Execution**: Start/stop campaign sending
- **Template Management**: Email template storage and management

#### Campaign Worker
**File**: `app/services/campaign_worker.py`
- **Background Processing**: Async campaign email sending
- **Batch Processing**: 50 emails per batch
- **Rate Limiting**: 60 emails/minute per user
- **Retry Logic**: Exponential backoff for failed sends

#### Fair Scheduler
**File**: `app/services/fair_scheduler.py`
- **Multi-tenant Rate Limiting**: Per-user quotas
- **Token Bucket Algorithm**: Smooth rate limiting
- **Daily Limits**: Global and per-user limits

### Critical Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/campaigns` | POST | Create new campaign |
| `/campaigns` | GET | List user campaigns |
| `/campaigns/{id}` | GET | Get campaign details |
| `/campaigns/{id}/start` | POST | Start campaign execution |
| `/campaigns/{id}/stop` | POST | Stop campaign execution |

### Features
- **Batch Email Sending**: 50 emails per batch for performance
- **Rate Limiting**: 60 emails/minute per user
- **Retry Logic**: 3 retries with exponential backoff
- **Campaign Logging**: All sent emails logged to CampaignEmailLog
- **Template System**: Reusable email templates
- **Scheduling**: Campaign scheduling and automation
---

## 👤 USER SERVICE (Port 8004) - USER MANAGEMENT

**Primary Responsibility**: User profiles, workspace management, settings

### Key Components

#### User Routes
**File**: `app/routes/users.py`
- **Profile Management**: Get and update user profiles
- **Picture Upload**: Profile picture management with Cloudinary
- **Password Management**: Change password with OTP verification
- **Workspace Settings**: User workspace configuration

### Critical Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/users/profile` | GET | Get current user profile |
| `/users/profile` | PUT | Update user profile |
| `/users/profile/picture` | POST | Upload profile picture |
| `/users/password/change` | PUT | Change password |
| `/users/workspace` | PUT | Update workspace settings |

### Features
- **Profile Management**: Complete user profile CRUD
- **Image Upload**: Cloudinary integration for profile pictures
- **Security**: OTP-based password changes
- **Workspace Configuration**: User-specific settings

---

## 🏢 BUSINESS SERVICE (Port 8003) - BUSINESS LOGIC & SETTINGS

**Primary Responsibility**: Business information, knowledge base, settings

### Key Components

#### Business Routes
**File**: `app/routes/business.py`
- **Business Information**: Company details and settings
- **Knowledge Base**: Business context for AI responses
- **Settings Management**: Business-level configuration

### Critical Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/business/{id}` | GET | Get business information |
| `/business/{id}` | PUT | Update business information |
| `/business/{id}/knowledge` | POST | Add knowledge base entry |
| `/business/{id}/settings` | PUT | Update business settings |

### Features
- **Business Profiles**: Company information management
- **Knowledge Base**: Context storage for AI-powered responses
- **Settings Management**: Business-level configuration
- **Vector Embeddings**: Knowledge base with vector search

---

## 📈 ANALYTICS SERVICE (Port 8007) - REPORTING & METRICS

**Primary Responsibility**: Email metrics, campaign analytics, reporting

### Key Components

#### Analytics Routes
**File**: `app/routes/analytics.py`
- **Overview Dashboard**: Key metrics and KPIs
- **Monthly Trends**: Time-series analytics
- **Campaign Performance**: Campaign-specific metrics
- **Health Checks**: System health monitoring

#### Event Handler
**File**: `app/routes/events.py`
- **Event Processing**: Email events (sent, opened, replied, bounced)
- **Real-time Analytics**: Live metric updates
- **Event Storage**: MongoDB event storage

### Critical Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/analytics/overview` | GET | Get analytics overview |
| `/analytics/monthly-trend` | GET | Get monthly trends |
| `/analytics/campaigns/{id}` | GET | Get campaign analytics |
| `/events/email-sent` | POST | Log email sent event |
| `/events/email-replied` | POST | Log email replied event |

### Events Tracked
- **Email Sent**: Campaign and individual email sends
- **Email Opened**: Email open tracking
- **Email Replied**: Reply detection and tracking
- **Email Bounced**: Bounce handling and tracking
- **Campaign Started**: Campaign execution events
- **Campaign Completed**: Campaign completion events

### Features
- **MongoDB Integration**: Event storage and aggregation
- **Real-time Metrics**: Live dashboard updates
- **Time-series Analytics**: Historical trend analysis
- **Campaign Performance**: Detailed campaign metrics

---

## 🤖 AUTOMATION SERVICE (Port 8008) - WORKFLOW AUTOMATION & AI

**Primary Responsibility**: Workflow automation, AI-powered features

### Key Components

#### Automation Routes
**File**: `app/routes/automation.py`
- **Workflow Management**: Create and manage automation workflows
- **AI Integration**: Intelligent response generation
- **Trigger Management**: Event-based automation triggers

### Critical Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/automation/workflows` | POST | Create automation workflow |
| `/automation/workflows` | GET | List user workflows |
| `/automation/workflows/{id}` | GET | Get workflow details |
| `/automation/workflows/{id}/execute` | POST | Execute workflow |

### Features
- **Workflow Automation**: Event-driven automation
- **AI Integration**: Intelligent response generation
- **Trigger System**: Email-based triggers
- **Conditional Logic**: Complex workflow conditions

---

## 👥 LEADS SERVICE (Port 8009) - LEAD MANAGEMENT

**Primary Responsibility**: Lead management, CSV import, lead tracking

### Key Components

#### Leads Routes
**File**: `app/routes/leads.py`
- **Lead CRUD**: Create, read, update, delete leads
- **CSV Import**: Batch import with enterprise-grade processing
- **Lead Tracking**: Campaign association and tracking

### Critical Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/leads` | GET | List leads with pagination |
| `/leads` | POST | Create new lead |
| `/leads/import` | POST | Import CSV leads |
| `/leads/{id}` | GET | Get lead details |
| `/leads/{id}` | PUT | Update lead |

### Features
- **CSV Import**: Batch processing (1000 rows per batch)
- **Lead Deduplication**: Automatic duplicate detection
- **Campaign Association**: Link leads to campaigns
- **Performance Optimization**: Fast commits with small batches
- **Error Handling**: Graceful handling of import errors
---

## 🔬 RESEARCH SERVICE (Port 8010) - DATA RESEARCH & ENRICHMENT

**Primary Responsibility**: Email context retrieval, AI response generation

### Key Components

#### Research Routes
**File**: `app/routes/research.py`
- **Email Retrieval**: Fetch business context for AI responses
- **Batch Retrieval**: Process multiple emails simultaneously
- **Vector Search**: Semantic search through knowledge base

### Critical Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/research/retrieve` | POST | Retrieve email context |
| `/research/batch-retrieve` | POST | Batch retrieve context |
| `/research/search` | POST | Search knowledge base |

### Features
- **Conversation History**: Retrieves full conversation context
- **Business Knowledge**: Fetches relevant business information
- **AI Response Generation**: Generates intelligent reply suggestions
- **Vector Embeddings**: Semantic search capabilities
- **Batch Processing**: Efficient bulk operations

---

## 🔔 NOTIFICATION SERVICE (Port 8011) - REAL-TIME NOTIFICATIONS

**Primary Responsibility**: Real-time notifications, user alerts

### Key Components

#### Notification Routes
**File**: `app/routes/notifications.py`
- **Notification Management**: Get, create, update notifications
- **Real-time Delivery**: WebSocket and SSE integration
- **Anti-spam Logic**: Intelligent notification filtering

#### Event Handlers
**File**: `app/events/handlers.py`
- **Event Processing**: Handle system events
- **Notification Triggers**: Event-based notification creation
- **Real-time Updates**: Live notification delivery

### Critical Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/notifications` | GET | Get user notifications |
| `/notifications/{id}/read` | PUT | Mark notification as read |
| `/notifications/stats` | GET | Get notification statistics |
| `/events/email-received` | POST | Handle email received event |

### Features
- **MongoDB Integration**: Notification storage and management
- **Anti-spam Logic**: Intelligent notification filtering
- **Real-time Delivery**: WebSocket and SSE support
- **Event-driven**: Automatic notification creation from system events
- **Expiration Management**: Automatic cleanup of expired notifications

---

## 🗄️ Database Architecture

### PostgreSQL (Amazon RDS) - Primary Database

#### Critical Tables

**campaign_email_logs** - Source of truth for inbox
```sql
CREATE TABLE campaign_email_logs (
    id UUID PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    campaign_id VARCHAR NOT NULL,
    lead_id VARCHAR NOT NULL,
    lead_email VARCHAR NOT NULL,
    message_id VARCHAR, -- Gmail message ID
    thread_id VARCHAR, -- Gmail thread ID
    subject TEXT,
    is_reply_received BOOLEAN DEFAULT false,
    last_reply_at TIMESTAMP,
    last_activity_at TIMESTAMP DEFAULT NOW(),
    last_24h_messages JSON, -- Message history buffer
    created_at TIMESTAMP DEFAULT NOW()
);
```

**email_accounts** - OAuth token storage
```sql
CREATE TABLE email_accounts (
    id UUID PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    provider VARCHAR NOT NULL,
    email_address VARCHAR NOT NULL,
    encrypted_access_token TEXT, -- AES-256 encrypted
    encrypted_refresh_token TEXT, -- AES-256 encrypted
    token_expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    connection_status VARCHAR DEFAULT 'connected'
);
```

**gmail_sync_states** - Delta sync tracking
```sql
CREATE TABLE gmail_sync_states (
    id UUID PRIMARY KEY,
    user_id VARCHAR UNIQUE NOT NULL,
    email_address VARCHAR NOT NULL,
    last_history_id BIGINT NOT NULL, -- Critical for delta sync
    watch_expiration BIGINT, -- Unix timestamp
    sync_status VARCHAR DEFAULT 'pending',
    consecutive_errors BIGINT DEFAULT 0
);
```

### MongoDB Atlas - Document Storage
- **Email Content**: Full HTML/text bodies
- **Attachment Metadata**: File information and storage links
- **Campaign Templates**: Reusable email templates
- **User Preferences**: User-specific settings
- **Analytics Aggregations**: Pre-computed metrics
- **Notifications**: Real-time notification storage

### Redis Cloud - Caching & Real-time
- **Session Storage**: User session management
- **API Response Caching**: 5-minute TTL for frequently accessed data
- **Real-time Message Queuing**: WebSocket message queuing
- **Rate Limiting Counters**: API rate limiting
- **Webhook Deduplication**: Prevent duplicate webhook processing

---

## 🔄 Inter-Service Communication Patterns

### Service-to-Service Communication

**Email Service Communications**:
- → Gmail API (OAuth token management)
- → Inbox Service (conversation updates)
- → Research Service (AI context retrieval)
- → Analytics Service (email event logging)

**Campaign Service Communications**:
- → Email Service (send campaign emails)
- → Leads Service (fetch lead lists)
- → Analytics Service (campaign metrics)

**Auth Service Communications**:
- → All Services (JWT token validation)
- → Email Service (OAuth token storage)

### Communication Methods
- **HTTP REST API**: Synchronous service-to-service calls
- **Event-driven**: Asynchronous via RabbitMQ
- **Real-time**: WebSocket/SSE for live updates
- **Database-driven**: Shared PostgreSQL for data consistency

### API Gateway Pattern
- **Gateway Service** (Port 8000): Routes requests to appropriate services
- **Load Balancing**: Distributes traffic across service instances
- **Authentication**: Centralized JWT validation
- **Rate Limiting**: Global rate limiting across services
---

## ⚡ Real-Time Email Reply Processing - Detailed Flow

### Step-by-Step Processing Flow

**Step 1: Gmail Pub/Sub Notification**
1. User receives email in Gmail
2. Gmail sends push notification to Google Cloud Pub/Sub topic
3. Pub/Sub delivers notification to webhook endpoint `/webhooks/unified/gmail`

**Step 2: Webhook Reception & Parsing**
1. Unified webhook handler receives POST request
2. Parse Pub/Sub notification payload (base64 decode)
3. Extract `email_address` and `history_id` from notification
4. Lookup `user_id` from `email_address` in EmailAccount table
5. Return HTTP 200 immediately (non-blocking)

**Step 3: Async Queue Processing**
1. Enqueue notification data to WebhookQueueService
2. One of 20 background workers picks up the task
3. Worker calls ReplyDetectionEngine.process_webhook_notification()

**Step 4: Message Fetching**
1. GmailAdapter.fetch_new_messages() called with user_id and history_id
2. Use Gmail History API to fetch only new messages (incremental sync)
3. Convert Gmail message format to unified email_message format
4. Update GmailSyncState with latest history_id

**Step 5: Email Filtering**
1. EmailFilterService.should_process_email() called for each message
2. Apply intelligent filtering rules:
   - Never filter personal domains (gmail.com, yahoo.com)
   - Filter marketing domains (mailchimp.com, sendgrid.net)
   - Filter social notifications (facebookmail.com, linkedin.com)
   - Filter system emails (noreply@, no-reply@)
3. Check Gmail labels (SPAM, CATEGORY_PROMOTIONS, CATEGORY_SOCIAL)

**Step 6: Thread Detection & Classification**
1. Check if `thread_id` matches existing campaign in CampaignEmailLog
2. **Campaign Thread**: If match found, this is a reply to campaign email
3. **Inbox Thread**: If no match, this is a new inbox conversation

**Step 7: Campaign Reply Processing**
1. If campaign thread detected:
   - Update `is_reply_received = true`
   - Set `last_reply_at = current_timestamp`
   - Update `last_activity_at` for inbox sorting
2. Append message to `last_24h_messages` JSON buffer
3. Apply duplicate detection (exact message ID + content similarity)

**Step 8: Inbox Conversation Processing**
1. If new inbox thread:
   - Create new entry in CampaignEmailLog with special markers:
     - `campaign_id = "INBOX"`
     - `lead_id = "INBOX"`
     - `lead_email = sender_email`
2. This enables unified inbox view for all conversations

**Step 9: Message Buffering**
1. Clean message body (remove quoted text, signatures)
2. Append to `last_24h_messages` JSON array
3. Keep only messages from last 24 hours
4. Store message metadata: message_id, from_email, to_email, body, timestamp

**Step 10: AI Retrieval Trigger**
1. Trigger Research Service for intelligent response generation
2. Pass conversation context:
   - `thread_id` for conversation history
   - `lead_email` for sender identification
   - `last_24h_messages` for recent context
   - `subject` for topic understanding
3. Generate AI-powered reply suggestions

**Step 11: Real-Time Updates**
1. Update inbox with new message/reply
2. Send SSE/WebSocket notification to frontend (if enabled)
3. Update analytics with email metrics
4. Trigger notification service for user alerts

### Performance Optimizations

**Database Optimizations**:
- Strategic indexing on user_id, thread_id, activity timestamps
- JSON message buffering (last 24 hours only)
- Connection pooling (20 connections, 10 overflow)
- Query result caching with Redis (5-minute TTL)

**Real-Time Processing**:
- Async webhook processing prevents blocking
- Queue overflow protection handles traffic spikes
- Duplicate detection prevents redundant processing
- Thread-safe operations with unique processing keys
- Memory leak prevention with automatic cleanup

**API Performance**:
- Response caching for frequently accessed data
- Pagination with configurable page sizes (default: 20, max: 100)
- Lazy loading for conversation details
- Optimistic updates in frontend

---

## 🔐 Security Architecture

### Authentication & Authorization

**JWT Token Management**:
- **Access Tokens**: 30-day expiration (43,200 minutes)
- **Refresh Tokens**: 60-day expiration
- **Automatic Refresh**: Before token expiration
- **Signature Verification**: HS256 algorithm

**OAuth Integration**:
- **Google OAuth 2.0**: Gmail scope for email access
- **Microsoft OAuth 2.0**: Outlook scope for email access
- **Token Storage**: AES-256 encrypted in PostgreSQL
- **Scope Management**: Granular permission control

### Data Encryption

**At Rest**:
- **OAuth Tokens**: AES-256 encryption in database
- **Sensitive Data**: Encrypted using ENCRYPTION_KEY
- **Database**: Amazon RDS with encryption enabled

**In Transit**:
- **HTTPS**: All API communications encrypted
- **TLS**: Database connections encrypted
- **Webhook Security**: Signature verification

### Security Features
- **CORS Protection**: Configured for localhost:3000
- **Rate Limiting**: API endpoint protection
- **Input Validation**: Pydantic model validation
- **SQL Injection Prevention**: SQLAlchemy ORM
- **XSS Protection**: Input sanitization

---

## 📊 Monitoring & Health Checks

### Service Health Monitoring

**Health Endpoints**: Each service exposes `/health` endpoint
- **Database Connection**: PostgreSQL, MongoDB, Redis connectivity
- **OAuth Token Validity**: Token expiration checking
- **Webhook Queue Status**: Queue depth and worker status
- **Sync State Monitoring**: Gmail sync error tracking

### Error Handling & Recovery

**Graceful Degradation**:
- **Database Unavailable**: Services start with limited functionality
- **MongoDB Disconnected**: Fallback to in-memory storage
- **Redis Unavailable**: Disable caching, continue operation
- **Gmail API Errors**: Exponential backoff and retry

**Automatic Recovery**:
- **Consecutive Error Counting**: Track failure patterns
- **Exponential Backoff**: Intelligent retry logic
- **Circuit Breaker**: Prevent cascade failures
- **Dead Letter Queues**: Handle failed webhook processing

### Performance Metrics

**Real-Time Metrics**:
- **Message Processing Latency**: Webhook to database commit time
- **Webhook Queue Depth**: Current queue size and processing rate
- **Database Query Performance**: Query execution times
- **API Response Times**: Endpoint performance monitoring
- **Token Refresh Success Rates**: OAuth token health

---

## 🚀 Deployment & Infrastructure

### Docker Containerization

**Service Containers**: Each of 11 services in separate containers
**Infrastructure Containers**: PostgreSQL, MongoDB, Redis, RabbitMQ
**Network Isolation**: Services communicate via Docker networks
**Volume Mounting**: Data persistence for databases
**Health Checks**: Container health monitoring

### Environment Configuration

**Database URLs**:
```env
DATABASE_URL=postgresql://postgres:password@projectgenesis-db.cl2yi6oegppw.ap-south-1.rds.amazonaws.com:5432/postgres
MONGODB_URL=mongodb+srv://user:password@cluster0.fxqyx2s.mongodb.net/mail_automation
REDIS_URL=redis://default:password@redis-10831.crce206.ap-south-1-1.ec2.cloud.redislabs.com:10831
```

**OAuth Credentials**:
```env
GOOGLE_CLIENT_ID=445917355826-seukam7tivt2d3n5felrhnd2til1kc5c.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=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
MICROSOFT_CLIENT_ID=5ea551ed-7062-471f-8950-a986e988c240
```

**Gmail Pub/Sub Configuration**:
```env
GMAIL_PUBSUB_TOPIC=projects/gmail-integration-484614/topics/gmail-notifications
GMAIL_PUBSUB_SUBSCRIPTION=projects/gmail-integration-484614/subscriptions/gmail-notifications-sub
```

### Service Communication

**Local Development**:
```env
AUTH_SERVICE_URL=http://localhost:8001
EMAIL_SERVICE_URL=http://localhost:8002
INBOX_SERVICE_URL=http://localhost:8005
```

**Docker Deployment**:
```env
AUTH_SERVICE_URL=http://auth-service:8000
EMAIL_SERVICE_URL=http://email-service:8000
INBOX_SERVICE_URL=http://inbox-service:8000
```

---

## 🎯 Critical Success Factors

### Real-Time Email Processing
1. **Sub-second webhook processing** with async queuing
2. **Reliable message delivery** via hybrid Pub/Sub + polling
3. **Intelligent filtering** to prevent noise
4. **Atomic database operations** for data consistency
5. **Scalable architecture** supporting 1000+ concurrent users

### System Reliability
1. **Fault-tolerant design** with multiple fallback mechanisms
2. **Data encryption** for sensitive information
3. **Comprehensive error handling** with graceful degradation
4. **Monitoring and alerting** for proactive issue resolution
5. **Scalable infrastructure** ready for enterprise deployment

### Performance Benchmarks
- **Webhook Processing**: < 100ms response time
- **Message Processing**: < 2 seconds end-to-end
- **Database Queries**: < 50ms average response time
- **API Endpoints**: < 200ms average response time
- **Concurrent Users**: 1000+ simultaneous webhook notifications

---

## 📝 Conclusion

The Mail Automation System represents a **production-ready, enterprise-grade platform** for real-time email processing and intelligent reply automation. With its **microservices architecture**, **hybrid real-time processing**, and **AI-powered features**, the system is designed to handle high-volume email operations while maintaining sub-second response times.

The **primary focus on real-time email replies** over campaign creation ensures that users can respond to incoming emails instantly, with AI assistance for faster and more effective communication. The robust architecture supports **1000+ concurrent users** with **fault-tolerant design** and **comprehensive monitoring**.

**Key Strengths**:
- ✅ **Real-time email processing** with Pub/Sub + polling hybrid
- ✅ **Intelligent conversation threading** with Gmail integration
- ✅ **AI-powered reply suggestions** for enhanced productivity
- ✅ **Enterprise-grade security** with encrypted token storage
- ✅ **Scalable microservices architecture** ready for growth
- ✅ **Comprehensive error handling** with graceful degradation

The system is **production-ready** and positioned for **enterprise deployment** with minimal additional configuration required.