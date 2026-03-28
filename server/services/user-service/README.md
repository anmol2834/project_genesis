# User Service - Celery Worker

## Overview
Handles background tasks for user profile embedding updates using Celery, Redis, and Qdrant.

## Prerequisites

### 1. Redis (Message Broker)
Already configured in `.env`:
```
REDIS_URL=redis://default:xWcYTzaXXRHcyKMZneOXfdfnzJduaNjy@redis-15835.crce217.ap-south-1-1.ec2.cloud.redislabs.com:15835
```

### 2. Qdrant Vector Database
**MUST be running locally before starting the worker**

Start Qdrant using Docker:
```bash
docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant
```

Or download and run locally from: https://qdrant.tech/documentation/quick-start/

Verify Qdrant is running:
```bash
curl http://localhost:6333/collections
```

## Starting the Worker

### Windows
```bash
cd server\services\user-service
start-worker.bat
```

The script will:
1. Check Qdrant connection
2. Create the `business_context` collection if needed
3. Start the Celery worker

### Manual Start
```bash
cd server\services\user-service
python init_qdrant.py  # Check Qdrant first
python -m celery -A celery_worker worker --loglevel=info --concurrency=2 --pool=solo
```

## Registered Tasks

- `user.update_user_embedding` - Updates user profile embeddings when AI context fields change

## Troubleshooting

### Error: "No connection could be made" (Qdrant)
**Cause**: Qdrant is not running

**Solution**:
```bash
docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant
```

### Error: "max number of clients reached" (Redis)
**Cause**: Too many Redis connections

**Solution**: 
- Fixed in code with connection pool limits
- Restart the worker
- Check for other services using the same Redis instance

### Error: "Received unregistered task of type 'auth.create_user_embedding'"
**Cause**: Auth service is sending tasks to the wrong queue

**Solution**: 
- This is expected - auth service has its own worker
- User service only handles `user.update_user_embedding`
- Each service should run its own Celery worker

### Worker Not Processing Tasks
**Check**:
1. Redis connection: `redis-cli -u <REDIS_URL> ping`
2. Qdrant connection: `curl http://localhost:6333/collections`
3. Task is registered: Look for "Registered tasks" in worker startup logs
4. Queue name matches: Both producer and consumer use `celery` queue

## Architecture

```
User Profile Update (API)
    ↓
Queue Task: user.update_user_embedding
    ↓
Celery Worker (this service)
    ↓
1. Fetch user from PostgreSQL
2. Generate embeddings (SentenceTransformer)
3. Upsert to Qdrant vector DB
```

## Configuration

All settings in `server/.env`:
- `CELERY_BROKER_URL` - Redis broker
- `CELERY_RESULT_BACKEND` - Redis results
- `QDRANT_URL` - Vector database URL (default: http://localhost:6333)
- `QDRANT_COLLECTION` - Collection name (default: business_context)
- `QDRANT_VECTOR_SIZE` - Vector dimensions (default: 384)

## Monitoring

Watch worker logs for:
- Task received: `Task user.update_user_embedding[...] received`
- Processing: `Partial embedding update for <user_id>`
- Success: `Updated N vectors for <user_id>`
- Errors: `ERROR/MainProcess` lines

## Performance

- Concurrency: 2 workers (solo pool for Windows)
- Retry: 3 attempts with exponential backoff
- Timeout: 5 minutes per task
- Connection pooling: Limited to 10 Redis connections
