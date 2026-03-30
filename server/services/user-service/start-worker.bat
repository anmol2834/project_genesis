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
