@echo off
REM User Service Celery Worker
REM Queue: user_queue
REM Task: user.update_user_embedding

echo ========================================
echo User Service - Celery Worker
echo ========================================
echo Queue: user_queue
echo Task: user.update_user_embedding
echo Purpose: Partial vector updates (AI fields only)
echo ========================================
echo.

cd /d "%~dp0"

REM Clear any stale session env vars so .env file values are always used
set CELERY_BROKER_URL=
set CELERY_RESULT_BACKEND=
set REDIS_URL=
set KAFKA_URL=
set REDIS_STREAMS_URL=

set PYTHONPATH=%~dp0;%~dp0\..\..;%PYTHONPATH%

python -m celery -A celery_worker worker ^
    --loglevel=warning ^
    --concurrency=1 ^
    --pool=solo ^
    -Q user_queue ^
    --without-mingle ^
    --without-gossip ^
    --without-heartbeat

pause
