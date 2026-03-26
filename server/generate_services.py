"""
Script to generate remaining microservice main.py files
"""

services = [
    ("inbox-service", 8005, "Inbox Management & Conversations"),
    ("campaign-service", 8006, "Campaign Management"),
    ("leads-service", 8007, "Lead Management"),
    ("analytics-service", 8008, "Analytics & Reporting"),
    ("automation-service", 8009, "Automation & Workflows"),
    ("research-service", 8010, "Research & Data Enrichment"),
    ("notification-service", 8011, "Notifications & Alerts"),
]

template = '''"""
{service_title} - {description}
Port: {port}
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from shared.config import get_config
from shared.logger import setup_logging, set_request_id, clear_request_id
from shared.database import init_database, close_database, check_database_health
from shared.cache import init_redis, close_redis, check_redis_health

logger = setup_logging("{service_name}")
config = get_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("{service_title} starting up...")
    await init_database()
    await init_redis()
    logger.info("{service_title} started successfully")
    yield
    logger.info("{service_title} shutting down...")
    await close_database()
    await close_redis()


app = FastAPI(title="{service_title}", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


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
    return JSONResponse(status_code=200 if (db_healthy and redis_healthy) else 503, content={{"status": "healthy" if (db_healthy and redis_healthy) else "unhealthy", "service": "{service_name}", "timestamp": datetime.utcnow().isoformat()}})


@app.get("/")
async def root():
    return {{"service": "{service_name}", "version": "1.0.0", "status": "running"}}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port={port}, reload=config.DEBUG)
'''

import os

for service_name, port, description in services:
    service_title = service_name.replace("-", " ").title()
    content = template.format(
        service_name=service_name,
        service_title=service_title,
        description=description,
        port=port
    )
    
    filepath = f"services/{service_name}/main.py"
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"Created {filepath}")

print("All services created successfully!")
