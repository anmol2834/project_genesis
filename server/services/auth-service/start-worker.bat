@echo off
REM Auth Service Celery Worker
REM Queue: auth_queue
REM Task: auth.create_user_embedding

echo ========================================
echo Auth Service - Celery Worker
echo ========================================
echo Queue: auth_queue
echo Task: auth.create_user_embedding
echo Purpose: Initial user embedding creation
echo ========================================
echo.

cd /d "%~dp0"

python -m celery -A celery_worker worker --loglevel=info --concurrency=2 --pool=solo -Q auth_queue

pause
