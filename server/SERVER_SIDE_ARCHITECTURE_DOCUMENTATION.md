# Mail Automation System - Server-Side Architecture Documentation

## 🎯 Executive Summary

Enterprise-grade microservices platform built with **Python FastAPI** for scalable email automation and management. The system features 12 independent microservices with shared infrastructure modules and cloud-native database solutions.

**Architecture**: Microservices + Event-Driven + Async-Ready  
**Language**: Python 3.11+  
**Framework**: FastAPI 0.109.0  
**Deployment**: Docker + Docker Compose

---

## 🏗️ System Architecture

### Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| **Backend Framework** | FastAPI | 0.109.0 |
| **Web Server** | Uvicorn | 0.27.0 |
| **Primary Database** | PostgreSQL (Amazon RDS) | asyncpg driver |
| **Document Store** | MongoDB Atlas | Motor 3.3.2 |
| **Cache & Broker** | Redis Cloud | redis 5.0.1 |
| **Task Queue** | Celery | 5.3.6 |
| **HTTP Client** | httpx | 0.26.0 |
| **Containerization** | Docker | docker-compose |

### Architecture Pattern

```
Client → Gateway Service (8000) → Microservices (8001-8011) → Shared Modules → Databases
```

### Core Design Principles

1. **Single Responsibility**: Each service handles one domain
2. **Shared Infrastructure**: Common modules (config, database, cache, logging)
3. **Async-First**: All I/O operations use async/await
4. **Configuration as Code**: Single .env file for all services
5. **Health Monitoring**: Every service exposes /health endpoint
6. **Containerized**: Docker-ready with orchestration

---

## 📁 Project Structure

```
server/
├── shared/                          # Shared infrastructure (ALL services use this)
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py              # Pydantic settings, loads .env
│   ├── database/
│   │   ├── __init__.py
│   │   ├── postgres.py              # Async PostgreSQL pool
│   │   └── mongodb.py               # Async MongoDB client
│   ├── cache/
│   │   ├── __init__.py
│   │   └── redis_client.py          # Async Redis with utilities
│   ├── celery/
│   │   ├── __init__.py
│   │   ├── celery_app.py            # Celery configuration
│   │   └── worker_config.py         # Worker setup
│   ├── logger/
│   │   ├── __init__.py
│   │   └── logging_config.py        # JSON logging + request ID
│   ├── utils/
│   │   ├── __init__.py
│   │   └── http_client.py           # Inter-service HTTP client
│   └── __init__.py
│
├── services/                        # 12 Microservices
│   ├── gateway-service/             # Port 8000
│   ├── auth-service/                # Port 8001
│   ├── user-service/                # Port 8002
│   ├── business-service/            # Port 8003
│   ├── email-service/               # Port 8004
│   ├── inbox-service/               # Port 8005
│   ├── campaign-service/            # Port 8006
│   ├── leads-service/               # Port 8007
│   ├── analytics-service/           # Port 8008
│   ├── automation-service/          # Port 8009
│   ├── research-service/            # Port 8010
│   ├── notification-service/        # Port 8011
│   └── base-requirements.txt
│
├── docker/
│   └── Dockerfile
├── logs/
│   └── README.md
├── .env                             # Single config file
├── docker-compose.yml               # Orchestration
├── Dockerfile                       # Base image
├── requirements.txt                 # Global dependencies
└── [utility scripts]                # start-all.bat, docker-*.bat
```

---

## 🛠️ Shared Infrastructure Layer

### 1. Configuration (`shared/config/settings.py`)

**Single source of truth** for all configuration.

**Key Features**:
- Pydantic Settings with type validation
- Loads from `.env` file (2 levels up from shared/config/)
- Auto-converts DATABASE_URL to async format
- Global config instance

**Configuration Structure**:
```python
class GlobalConfig(BaseSettings):
    # Databases
    DATABASE_URL: str                    # PostgreSQL
    MONGODB_URL: str                     # MongoDB
    REDIS_URL: str                       # Redis
    
    # Service URLs (12 services)
    GATEWAY_SERVICE_URL: str
    AUTH_SERVICE_URL: str
    # ... all 12 services
    
    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 60
    
    # OAuth
    GOOGLE_CLIENT_ID: Optional[str]
    GOOGLE_CLIENT_SECRET: Optional[str]
    MICROSOFT_CLIENT_ID: Optional[str]
    MICROSOFT_CLIENT_SECRET: Optional[str]
    
    # Celery
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str
    
    # Application
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: List[str]
    
    # Performance
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    REDIS_MAX_CONNECTIONS: int = 50
    WORKER_CONCURRENCY: int = 4
```

**Usage**:
```python
from shared.config import get_config
config = get_config()
```

### 2. Database (`shared/database/`)

#### PostgreSQL (`postgres.py`)

**Async connection pool** using SQLAlchemy + asyncpg.

**Features**:
- Async engine with connection pooling (20 connections, 10 overflow)
- Session management via async context manager
- AWS RDS SSL support
- Pool pre-ping and recycling (3600s)

**Usage**:
```python
from shared.database import get_db_session, init_database, close_database

# Initialize on startup
await init_database()

# Use session
async with get_db_session() as session:
    result = await session.execute(query)
    await session.commit()

# Close on shutdown
await close_database()
```

#### MongoDB (`mongodb.py`)

**Async MongoDB** using Motor driver.

**Features**:
- Motor async client
- Connection pooling (50 max, 10 min)
- MongoDB Atlas optimized
- Retry logic

**Usage**:
```python
from shared.database import get_mongo_database, init_mongodb

await init_mongodb()
db = get_mongo_database()
collection = db["users"]
doc = await collection.find_one({"email": "user@example.com"})
```

### 3. Cache (`shared/cache/redis_client.py`)

**Async Redis** for caching and sessions.

**Features**:
- redis-py with asyncio
- Connection pooling (50 max)
- Auto-retry on timeout
- UTF-8 encoding

**Usage**:
```python
from shared.cache import get_cached, set_cached, init_redis

await init_redis()
value = await get_cached("key")
await set_cached("key", "value", ttl=300)  # 5 min TTL
```

### 4. Celery (`shared/celery/`)

**Task queue** with Redis broker.

**Configuration**:
- Task serialization: JSON
- Worker prefetch: 1
- Task time limit: 300s (5 min)
- Result expires: 3600s (1 hour)

**Usage**:
```python
from shared.celery import get_celery_app, init_celery

init_celery()
app = get_celery_app()
```

### 5. Logger (`shared/logger/logging_config.py`)

**Structured logging** with request ID tracking.

**Features**:
- JSON logging (production) or human-readable (dev)
- Request ID context variable
- Thread-safe
- Configurable log levels

**Usage**:
```python
from shared.logger import setup_logging, get_logger, set_request_id

logger = setup_logging("service-name")
logger = get_logger(__name__)
logger.info("Message", extra={"user_id": "123"})

request_id = set_request_id()  # Auto-generate UUID
```

### 6. Utils (`shared/utils/http_client.py`)

**HTTP client** for inter-service communication.

**Features**:
- httpx async client
- Connection pooling (100 max, 20 keepalive)
- 30s timeout
- Service discovery

**Usage**:
```python
from shared.utils import get_service_client

auth_client = get_service_client("auth")
response = await auth_client.get("/users/me", headers={...})

email_client = get_service_client("email")
await email_client.post("/send", json_data={...})
```

---

## 💻 Microservices Portfolio

| Service | Port | Responsibility |
|---------|------|----------------|
| **gateway-service** | 8000 | API Gateway, routing |
| **auth-service** | 8001 | JWT auth, OAuth (Google/Microsoft) |
| **user-service** | 8002 | User profiles, settings |
| **business-service** | 8003 | Business logic, knowledge base |
| **email-service** | 8004 | Gmail/Outlook integration |
| **inbox-service** | 8005 | Inbox, conversation threading |
| **campaign-service** | 8006 | Email campaigns |
| **leads-service** | 8007 | Lead management, CSV import |
| **analytics-service** | 8008 | Reporting, metrics |
| **automation-service** | 8009 | Workflow automation, AI |
| **research-service** | 8010 | Data research, enrichment |
| **notification-service** | 8011 | Real-time notifications |

### Common Service Structure

All services follow this template:

```python
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import sys, os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from shared.config import get_config
from shared.logger import setup_logging, set_request_id, clear_request_id
from shared.database import init_database, close_database, check_database_health
from shared.cache import init_redis, close_redis, check_redis_health
from shared.utils import close_http_client

logger = setup_logging("service-name")
config = get_config()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Service starting...")
    await init_database()
    await init_redis()
    logger.info("Service started")
    yield
    # Shutdown
    logger.info("Service shutting down...")
    await close_database()
    await close_redis()
    await close_http_client()
    logger.info("Service stopped")

app = FastAPI(title="Service", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = set_request_id()
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        clear_request_id()

@app.get("/health")
async def health_check():
    db_healthy = await check_database_health()
    redis_healthy = await check_redis_health()
    return {
        "status": "healthy" if (db_healthy and redis_healthy) else "unhealthy",
        "service": "service-name",
        "checks": {
            "database": "healthy" if db_healthy else "unhealthy",
            "redis": "healthy" if redis_healthy else "unhealthy"
        }
    }

@app.get("/")
async def root():
    return {"service": "service-name", "version": "1.0.0", "status": "running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=config.DEBUG)
```

### Service Lifecycle

**Startup**:
1. Load .env configuration
2. Setup logging
3. Initialize PostgreSQL connection
4. Initialize MongoDB connection
5. Initialize Redis connection
6. Register routes/middleware
7. Start accepting requests

**Shutdown**:
1. Stop accepting requests
2. Complete in-flight requests
3. Close HTTP client
4. Close Redis
5. Close databases
6. Flush logs

---

## 🔐 Environment Configuration

### .env File Structure

```env
# Database
DATABASE_URL=postgresql://user:pass@host:5432/db
MONGODB_URL=mongodb+srv://user:pass@cluster/db
REDIS_URL=redis://default:pass@host:port

# Service URLs (Internal)
GATEWAY_SERVICE_URL=http://gateway-service:8000
AUTH_SERVICE_URL=http://auth-service:8000
# ... all 12 services

# JWT
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=43200
JWT_REFRESH_TOKEN_EXPIRE_DAYS=60

# Encryption
ENCRYPTION_KEY=base64-encoded-key

# OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-secret
MICROSOFT_CLIENT_ID=your-microsoft-client-id
MICROSOFT_CLIENT_SECRET=your-microsoft-secret

# Celery
CELERY_BROKER_URL=redis://host:port/1
CELERY_RESULT_BACKEND=redis://host:port/2

# Application
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO
CORS_ORIGINS=["http://localhost:3000"]

# Performance
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10
REDIS_MAX_CONNECTIONS=50
WORKER_CONCURRENCY=4

# Rate Limiting
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_BURST=10
```

---

## 🐳 Docker Deployment

### docker-compose.yml

All 12 services defined with:
- Shared network: `mailautomation-network`
- Volume mounting for hot-reload
- Environment injection
- Restart policy: `unless-stopped`

**Service Template**:
```yaml
service-name:
  build:
    context: .
    dockerfile: Dockerfile
  container_name: service-name
  working_dir: /app/services/service-name
  command: uvicorn main:app --host 0.0.0.0 --port 8000
  ports:
    - "8000:8000"
  volumes:
    - ./services/service-name:/app/services/service-name
    - ./shared:/app/shared
    - ./.env:/app/.env
  environment:
    - PYTHONPATH=/app
  networks:
    - microservices-network
  restart: unless-stopped
```

### Commands

```bash
# Start all services
docker-compose up --build

# Start specific services
docker-compose up gateway-service auth-service

# View logs
docker-compose logs -f service-name

# Stop all
docker-compose down

# Health check
docker-compose ps
```

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run service
cd services/gateway-service
python main.py

# Or use scripts
./run.sh  # Linux/Mac
run.bat   # Windows
```

---

## 🗄️ Database Architecture

### PostgreSQL (Amazon RDS)

**Connection**: `projectgenesis-db.cl2yi6oegppw.ap-south-1.rds.amazonaws.com:5432`

**Pool Configuration**:
- Pool size: 20
- Max overflow: 10
- Timeout: 30s
- Pre-ping: Enabled
- Recycle: 3600s

**Usage**: User accounts, business data, campaigns, leads, transactional data

### MongoDB Atlas

**Connection**: `cluster0.fxqyx2s.mongodb.net/mailautomation`

**Pool Configuration**:
- Max pool: 50
- Min pool: 10
- Idle timeout: 45s

**Usage**: Email content, attachments, analytics events, notifications

### Redis Cloud

**Connection**: `redis-10831.crce206.ap-south-1-1.ec2.cloud.redislabs.com:10831`

**Pool Configuration**:
- Max connections: 50
- Socket timeout: 5s

**Usage**:
- DB 0: General caching
- DB 1: Celery broker
- DB 2: Celery results

---

## 🔄 Inter-Service Communication

### Patterns

1. **HTTP REST** (Synchronous): Service-to-service via httpx
2. **Shared Database** (Consistency): All services access PostgreSQL
3. **Celery Tasks** (Asynchronous): Background jobs via Redis

### Service Discovery

Configuration-based URLs in .env:
```python
from shared.utils import get_service_client

client = get_service_client("auth")  # Resolves to AUTH_SERVICE_URL
response = await client.get("/endpoint")
```

### Request Tracing

- Request ID generated at entry point
- Stored in context variable
- Added to all logs
- Returned in `X-Request-ID` header
- Passed to downstream services

---

## 🔒 Security

### Authentication

**JWT**:
- Algorithm: HS256
- Access token: 30 days
- Refresh token: 60 days

**OAuth 2.0**:
- Google: Gmail integration
- Microsoft: Outlook integration
- Tokens encrypted (AES-256) in PostgreSQL

### Encryption

**At Rest**:
- OAuth tokens: AES-256
- Database: RDS encryption

**In Transit**:
- HTTPS for APIs
- TLS for databases
- SSL for RDS

### Protection

- CORS: Configured origins
- Rate limiting: 60 req/min
- Input validation: Pydantic
- SQL injection: SQLAlchemy ORM

---

## 📦 Dependencies

### Global (requirements.txt)

**Framework**:
- fastapi==0.109.0
- uvicorn[standard]==0.27.0
- pydantic==2.5.3
- pydantic-settings==2.1.0

**Databases**:
- sqlalchemy==2.0.25
- asyncpg==0.29.0
- motor==3.3.2
- pymongo==4.6.1

**Cache/Queue**:
- redis==5.0.1
- celery==5.3.6

**HTTP**:
- httpx==0.26.0

**Security**:
- python-jose[cryptography]==3.3.0
- passlib[bcrypt]==1.7.4
- cryptography==42.0.0

**Utils**:
- python-dotenv==1.0.0
- structlog==24.1.0

---

## 📊 Monitoring

### Health Checks

Every service: `GET /health`

Response:
```json
{
  "status": "healthy",
  "service": "service-name",
  "timestamp": "2024-03-24T10:30:00Z",
  "checks": {
    "database": "healthy",
    "redis": "healthy"
  }
}
```

### Metrics

- Message processing latency
- Database query performance
- API response times
- Queue depth
- Token refresh rates

---

## 🎯 Summary

**Architecture**: 12 microservices + shared infrastructure  
**Pattern**: Async-first with event-driven capabilities  
**Deployment**: Docker containerized  
**Databases**: PostgreSQL (primary), MongoDB (documents), Redis (cache/queue)  
**Security**: JWT + OAuth 2.0 + AES-256 encryption  
**Monitoring**: Health checks + structured logging  

**Key Strengths**:
- ✅ Clean separation of concerns
- ✅ Shared infrastructure reduces duplication
- ✅ Async/await throughout
- ✅ Type-safe configuration
- ✅ Production-ready with Docker
- ✅ Comprehensive health monitoring
