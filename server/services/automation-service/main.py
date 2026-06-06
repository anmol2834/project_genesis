#!/usr/bin/env python3
"""
Automation Service - Entry Point
==================================
Delegates to app/main.py (the production application module).

Run with:
    python main.py
or:
    uvicorn app.main:app --host 0.0.0.0 --port 8009
"""
import sys
import os

# ── Path setup: server root must be on sys.path for shared.* imports ─────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.abspath(os.path.join(BASE_DIR, "../.."))
sys.path.insert(0, SERVER_DIR)
sys.path.insert(0, BASE_DIR)
# ─────────────────────────────────────────────────────────────────────────────

# Re-export app from the production module so uvicorn can find it at main:app
from app.main import app  # noqa: F401 — re-export for uvicorn main:app


if __name__ == "__main__":
    import uvicorn
    from app.core.config import initialize_config

    config = initialize_config()
    port = config.service.service_port

    print(f"\nStarting automation-service on port {port}")
    print(f"   Environment: {config.shared.ENVIRONMENT}\n")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
        timeout_keep_alive=30,
        backlog=2048,
    )
