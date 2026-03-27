# Auth Service

**Enterprise-grade authentication service with AI-powered user context embeddings**

---

## 🎯 Purpose

Handles user authentication, JWT token management, and AI context generation for personalized email automation.

---

## ✨ Features

- ⚡ **Fast Signup** - Response in <200ms
- 🔐 **Secure Authentication** - bcrypt password hashing + JWT tokens
- 🧠 **AI Context Embeddings** - Automatic user context vectorization
- 🔄 **Async Processing** - Background embedding generation with Celery
- 🔁 **Fault Tolerant** - Automatic retry with exponential backoff
- 🔒 **Multi-Tenant Safe** - Strict user data isolation
- 📊 **Production Ready** - Comprehensive logging and monitoring

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Auth Service (Port 8001)               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  API Layer                                                  │
│  ├── POST /auth/signup     (Signup endpoint)               │
│  ├── GET  /health          (Health check)                  │
│  └── GET  /                (Service info)                  │
│                                                             │
│  Business Logic                                             │
│  ├── Password hashing (bcrypt)                             │
│  ├── JWT token generation (HS256)                          │
│  ├── User validation (Pydantic)                            │
│  └── Database operations (SQLAlchemy)                      │
│                                                             │
│  Background Tasks (Celery)                                  │
│  └── Embedding generation (sentence-transformers)          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
   PostgreSQL              Redis              Qdrant
   (User Data)        (Task Queue)      (Vector Storage)
```

---

## 📁 Project Structure

```
auth-service/
├── api/
│   ├── __init__.py
│   └── auth.py                 # Signup endpoint
├── models/
│   ├── __init__.py
│   └── user.py                 # User model (PostgreSQL)
├── schemas/
│   ├── __init__.py
│   └── auth.py                 # Pydantic schemas
├── services/
│   ├── __init__.py
│   └── embedding_service.py    # Embedding generation
├── tasks/
│   ├── __init__.py
│   └── embedding_tasks.py      # Celery tasks
├── utils/
│   ├── __init__.py
│   ├── password.py             # Password hashing
│   └── jwt.py                  # JWT utilities
├── main.py                     # FastAPI app
├── celery_worker.py            # Celery worker
├── test_signup.py              # Test suite
├── SIGNUP_SYSTEM_DOCUMENTATION.md
├── QUICK_START.md
└── README.md
```

---

## 🚀 Quick Start

### 1. Start Service
```bash
docker-compose up auth-service -d
```

### 2. Start Celery Worker
```bash
cd services/auth-service
start-celery-worker.bat
```

### 3. Test Signup
```bash
curl -X POST http://localhost:8001/auth/signup \
  -H "Content-Type: application/json" \
  -d @test_data.json
```

See [QUICK_START.md](QUICK_START.md) for detailed instructions.

---

## 📊 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/signup` | User signup with AI context |
| GET | `/health` | Service health check |
| GET | `/` | Service information |

---

## 🔐 Security

- **Password**: bcrypt with auto-salt
- **JWT**: HS256 algorithm
- **Access Token**: 30 days
- **Refresh Token**: 60 days
- **Multi-Tenant**: User ID filtering on all queries

---

## 🧠 AI Embeddings

- **Model**: sentence-transformers/all-MiniLM-L6-v2
- **Vector Size**: 384 dimensions
- **Storage**: Qdrant vector database
- **Chunks**: 5 specialized embeddings per user
  - Business Core
  - Target Audience
  - Communication Tone
  - Use Cases
  - AI Instructions

---

## 📦 Dependencies

- **FastAPI** - Web framework
- **SQLAlchemy** - ORM
- **asyncpg** - PostgreSQL driver
- **Redis** - Task queue
- **Celery** - Background tasks
- **sentence-transformers** - Embeddings
- **Qdrant** - Vector database
- **passlib** - Password hashing
- **python-jose** - JWT tokens

---

## 🧪 Testing

```bash
# Run all tests
pytest test_signup.py -v

# Run specific test
pytest test_signup.py::test_signup_success -v

# With coverage
pytest test_signup.py --cov=. --cov-report=html
```

---

## 📊 Performance

| Metric | Target | Actual |
|--------|--------|--------|
| Signup Response | <200ms | ~150ms |
| Database Write | <50ms | ~30ms |
| JWT Generation | <10ms | ~5ms |
| Embedding (Async) | N/A | ~2-3s |

---

## 📝 Logging

All operations logged with structured JSON:
```json
{
  "timestamp": "2024-01-01T00:00:00Z",
  "level": "INFO",
  "service": "auth-service",
  "request_id": "uuid",
  "message": "User created successfully",
  "user_id": "uuid"
}
```

---

## 🔧 Configuration

Environment variables in `.env`:
```env
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
JWT_SECRET_KEY=...
QDRANT_URL=http://qdrant:6333
```

---

## 📚 Documentation

- [Signup System Documentation](SIGNUP_SYSTEM_DOCUMENTATION.md) - Complete technical docs
- [Quick Start Guide](QUICK_START.md) - Getting started
- [Server Architecture](../../SERVER_SIDE_ARCHITECTURE_DOCUMENTATION.md) - Overall system

---

## 🛠️ Development

### Local Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Run service
python main.py

# Run worker
celery -A tasks.embedding_tasks worker --loglevel=info
```

### Docker Setup
```bash
# Build
docker-compose build auth-service

# Run
docker-compose up auth-service -d

# Logs
docker logs -f auth-service
```

---

## 🐛 Troubleshooting

See [QUICK_START.md](QUICK_START.md#-debugging) for common issues and solutions.

---

## 🎯 Roadmap

- [x] User signup with validation
- [x] Password hashing (bcrypt)
- [x] JWT token generation
- [x] AI embedding generation
- [x] Celery background tasks
- [x] Multi-tenant isolation
- [ ] User login
- [ ] Token refresh
- [ ] Email verification (OTP)
- [ ] OAuth (Google, Microsoft)
- [ ] Password reset
- [ ] Profile update

---

## 👥 Contributing

1. Follow existing code structure
2. Add tests for new features
3. Update documentation
4. Ensure <200ms response time
5. Maintain security standards

---

## 📄 License

Proprietary - Mail Automation System

---

## 🆘 Support

- Technical Issues: Check logs and documentation
- Architecture Questions: See SERVER_SIDE_ARCHITECTURE_DOCUMENTATION.md
- Qdrant Issues: See QDRANT_SETUP_GUIDE.md

---

**Built with ❤️ by the Backend Team**
