#!/usr/bin/env python3
"""
Automation Service - Main Entry Point
======================================
Enterprise AI automation platform with 10-stage pipeline.
"""
import sys
import os
import asyncio
from contextlib import asynccontextmanager

# Setup paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.abspath(os.path.join(BASE_DIR, "../.."))
sys.path.insert(0, SERVER_DIR)
sys.path.insert(0, BASE_DIR)

# Import after path setup
from fastapi import FastAPI
from shared.config import get_config

# Global worker runtime reference
worker_runtime_task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan manager"""
    global worker_runtime_task
    
    print("=" * 70)
    print("AUTOMATION-SERVICE STARTING")
    print("=" * 70)
    
    # Initialize resources with error handling
    print("Initializing resources...")
    try:
        from app.core.resource_management import initialize_resources
        await initialize_resources()
        print("Resources initialized successfully")
    except Exception as e:
        print(f"WARNING: Resource initialization had issues: {e}")
        print("Continuing with limited functionality...")
    
    # Start worker runtime
    print("Starting worker runtime...")
    try:
        from app.workers.runtime import get_worker_runtime
        worker_runtime = get_worker_runtime()
        worker_runtime_task = asyncio.create_task(worker_runtime.run())
        print("Worker runtime started")
    except Exception as e:
        print(f"WARNING: Worker runtime failed to start: {e}")
    
    print("=" * 70)
    print("AUTOMATION-SERVICE READY")
    print("=" * 70)
    print("")
    print("Pipeline Stages:")
    print("  1. Conversation Memory Engine")
    print("  2. Intent Understanding (ChatGPT Brain #1)")
    print("  3. Query Planning")
    print("  4. Multi-Stage Retrieval")
    print("  5. Context Validation + Compression")
    print("  6. Grounded Prompt Builder")
    print("  7. LLM Reasoning (ChatGPT Brain #2)")
    print("  8. Hallucination Guard")
    print("  9. Confidence + Risk Engine")
    print("  10. Human Handoff OR Send Reply")
    print("=" * 70)
    
    yield
    
    # Shutdown
    print("\n" + "=" * 70)
    print("AUTOMATION-SERVICE SHUTTING DOWN")
    print("=" * 70)
    
    if worker_runtime_task:
        worker_runtime_task.cancel()
        try:
            await worker_runtime_task
        except asyncio.CancelledError:
            pass
    
    try:
        from app.core.resource_management import shutdown_resources
        await shutdown_resources()
    except Exception as e:
        print(f"Shutdown warning: {e}")
    
    print("Shutdown complete")

# Create FastAPI app
app = FastAPI(
    title="Automation Service",
    version="2.0.0",
    lifespan=lifespan
)

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "automation-service",
        "version": "2.0.0"
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "automation-service",
        "version": "2.0.0",
        "pipeline": [
            "Conversation Memory Engine",
            "Intent Understanding (ChatGPT Brain #1)",
            "Query Planning",
            "Multi-Stage Retrieval",
            "Context Validation + Compression",
            "Grounded Prompt Builder",
            "LLM Reasoning (ChatGPT Brain #2)",
            "Hallucination Guard",
            "Confidence + Risk Engine",
            "Human Handoff OR Send Reply"
        ]
    }

@app.get("/pipeline/status")
async def pipeline_status():
    """Get pipeline status"""
    try:
        from app.core.resource_management import get_resource_manager
        manager = get_resource_manager()
        health = await manager.health_check()
        return {
            "status": "operational",
            "resources": health,
            "pipeline_stages": 10
        }
    except Exception as e:
        return {
            "status": "degraded",
            "error": str(e),
            "pipeline_stages": 10
        }

if __name__ == "__main__":
    import uvicorn
    
    config = get_config()
    port = 8009
    
    print(f"\nStarting automation-service on port {port}")
    print(f"   Environment: {config.ENVIRONMENT}")
    print()
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )
