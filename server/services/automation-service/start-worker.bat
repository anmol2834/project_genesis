@echo off
echo ========================================
echo Automation Service - Celery Worker
echo ========================================
echo Queue: automation_queue
echo Tasks: learning_engine (cycle, expire, cache, cleanup)
echo ========================================

cd /d "%~dp0"
python -m celery -A celery_worker worker --loglevel=info -Q automation_queue --concurrency=2

pause
