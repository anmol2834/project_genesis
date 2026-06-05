# Automation Service v2.0

## Overview

Enterprise-grade AI automation platform with near-zero hallucination RAG, designed for ultra-fast multi-tenant AI automation at scale.

## Key Features

- **Ultra-fast pipeline**: <5s end-to-end latency with aggressive caching
- **Near-zero hallucination**: Grounded-only LLM generation with validation
- **Multi-tenant isolation**: Every layer enforces tenant boundaries
- **Horizontal scalability**: Stateless workers, event-driven architecture
- **Enterprise reliability**: Exactly-once delivery via Redis consumer groups
- **Memory-driven reasoning**: Conversation continuity across turns
- **L1-L7 hierarchical retrieval**: Cache-first with early exit optimization

## Architecture

```
Email Service → Redis Streams → Automation Service → Response
                                       ↓
                    Memory → Intelligence → Retrieval → LLM → Handoff
```

## Project Structure

```
automation-service/
├── app/
│   ├── api/              # HTTP endpoints (health, metrics, admin)
│   ├── core/             # Infrastructure (config, logging, security)
│   ├── orchestration/    # Pipeline coordinator
│   ├── memory/           # Conversation continuity (hot/cold memory)
│   ├── intelligence/     # Intent understanding & query planning
│   ├── retrieval/        # L1-L7 hierarchical retrieval engine
│   ├── llm/              # Grounded generation with hallucination guard
│   ├── handoff/          # Intelligent escalation to humans
│   ├── messaging/        # Redis Streams consumer/producer
│   ├── integrations/     # External service clients (OpenAI, Qdrant)
│   ├── models/           # Domain models, DTOs, schemas
│   ├── storage/          # Repositories, caching, persistence
│   ├── workers/          # Background workers (embedding, cleanup)
│   ├── observability/    # Metrics, tracing, logs, alerts
│   └── tests/            # Unit, integration, performance tests
├── docs/                 # Architecture documentation
├── scripts/              # Deployment and utility scripts
├── deployments/          # Kubernetes manifests
├── docker/               # Dockerfiles
└── requirements/         # Python dependencies
```

## Quick Start

### Prerequisites

- Python 3.11+
- Redis (Upstash or local)
- PostgreSQL 15+
- Qdrant (cloud or self-hosted)
- OpenAI API key

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Run service
python -m app.main
```

### Docker

```bash
docker build -t automation-service:2.0.0 .
docker run -p 8009:8009 --env-file .env automation-service:2.0.0
```

### Kubernetes

```bash
kubectl apply -f deployments/k8s/
```

## Configuration

See `.env.example` for all configuration options.

Key environment variables:

```bash
# Service
SERVICE_PORT=8009
WEB_CONCURRENCY=4
WORKER_CONCURRENCY=16

# Redis
REDIS_URL=rediss://your-redis.upstash.io:6379

# PostgreSQL
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db

# Qdrant
QDRANT_URL=https://your-qdrant.cloud:6333

# OpenAI
OPENAI_API_KEY=sk-xxx
```

## Development

### Running Tests

```bash
# Unit tests
pytest app/tests/unit/

# Integration tests
pytest app/tests/integration/

# Performance tests
pytest app/tests/performance/
```

### Code Quality

```bash
# Format
black app/

# Lint
ruff app/

# Type check
mypy app/
```

## Deployment

See [docs/ARCHITECTURE_IMPLEMENTATION.md](docs/ARCHITECTURE_IMPLEMENTATION.md) for detailed deployment strategies.

### Production Checklist

- [ ] Multi-worker deployment (4+ workers)
- [ ] Redis consumer group configured
- [ ] Database connection pooling tuned
- [ ] Prometheus metrics exported
- [ ] Grafana dashboards deployed
- [ ] Alerts configured (PagerDuty/Slack)
- [ ] GPU workers for embeddings (optional)
- [ ] Horizontal pod autoscaling enabled

## Monitoring

### Health Check

```bash
curl http://localhost:8009/health
```

### Metrics

```bash
curl http://localhost:8009/metrics
```

### Logs

Structured JSON logs with correlation IDs:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "message": "Processing message",
  "user_id": "abc12345",
  "conversation_id": "conv-123",
  "request_id": "req-xyz789"
}
```

## Performance

### Target Metrics

- **Latency**: <5s p95, <3s p50
- **Throughput**: 1M+ conversations/day per 50 workers
- **Cache hit rate**: >80% (combined L1+L2+response cache)
- **Error rate**: <0.5%
- **Escalation rate**: <10%

### Scaling

- **Horizontal**: Add workers (stateless architecture)
- **Vertical**: Add GPUs for embeddings/reranking
- **Caching**: Redis cluster for higher throughput
- **Database**: Read replicas for query scaling

## Documentation

- [Architecture Implementation](docs/ARCHITECTURE_IMPLEMENTATION.md) - Complete system design
- [Orchestration Layer](app/orchestration/README.md) - Pipeline coordination
- [Memory Layer](app/memory/README.md) - Conversation continuity
- [Intelligence Layer](app/intelligence/README.md) - Intent understanding
- [Retrieval Layer](app/retrieval/README.md) - Data fetching strategies
- [LLM Layer](app/llm/README.md) - Grounded generation
- [Handoff Layer](app/handoff/README.md) - Intelligent escalation
- [Messaging Layer](app/messaging/README.md) - Event processing

## Contributing

This is an internal enterprise service. Contact the AI Platform team for contribution guidelines.

## License

Proprietary - Internal Use Only

## Support

- **Slack**: #ai-automation-platform
- **Email**: ai-platform@company.com
- **On-call**: PagerDuty rotation

---

**Version**: 2.0.0  
**Status**: Phase 1 Complete (Folder Structure + Architecture)  
**Next Phase**: Phase 2 - Messaging Layer Implementation
