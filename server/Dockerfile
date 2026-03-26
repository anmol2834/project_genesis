# Base Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (better caching)
RUN pip install --no-cache-dir \
    fastapi==0.109.0 \
    uvicorn[standard]==0.27.0 \
    pydantic==2.5.3 \
    pydantic-settings==2.1.0 \
    sqlalchemy==2.0.25 \
    asyncpg==0.29.0 \
    psycopg2-binary==2.9.9 \
    pymongo==4.6.1 \
    motor==3.3.2 \
    redis==5.0.1 \
    hiredis==2.3.2 \
    celery==5.3.6 \
    kombu==5.3.5 \
    httpx==0.26.0 \
    aiohttp==3.9.1 \
    python-dotenv==1.0.0 \
    python-jose[cryptography]==3.3.0 \
    passlib[bcrypt]==1.7.4 \
    cryptography==42.0.0 \
    pyyaml==6.0.1 \
    python-dateutil==2.8.2 \
    structlog==24.1.0 \
    qdrant-client==1.7.0 \
    google-auth==2.23.4 \
    google-auth-oauthlib==1.1.0 \
    google-auth-httplib2==0.1.1

# Copy shared modules
COPY shared/ /app/shared/

# Copy .env file
COPY .env /app/.env

# Expose port (will be overridden by docker-compose)
EXPOSE 8000

# Default command (will be overridden by docker-compose)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
