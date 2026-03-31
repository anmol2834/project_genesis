"""
Automation Service — Celery Worker
====================================
Runs the learning engine periodic tasks:
  - Learning cycle (every 6h): compute insights from feedback logs
  - Expire pending (every 2h): mark stale pending logs as ignored
  - Push cache (every 6h):     push insights to Redis
  - Cleanup logs (daily):      delete logs older than 90 days

Start this worker alongside the FastAPI service:
  python -m celery -A celery_worker worker --loglevel=info -Q automation_queue

Start Beat scheduler (for periodic tasks):
  python -m celery -A celery_worker beat --loglevel=info
"""
import sys
import os

# Ensure shared modules are importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from shared.celery import get_celery_app
from learning_engine.scheduler import register_beat_schedule

# Get the shared Celery app and register learning engine tasks + beat schedule
celery_app = get_celery_app()
register_beat_schedule()

# Expose as 'app' so Celery CLI can find it:  celery -A celery_worker worker
app = celery_app
