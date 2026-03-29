@echo off
REM ============================================================
REM  Email Service — Celery Worker
REM  Uses "python -m celery" to avoid PATH issues on Windows
REM ============================================================

echo ============================================================
echo  Email Service Celery Worker
echo ============================================================
echo  Broker  : Redis (see server/.env CELERY_BROKER_URL)
echo  Queues  : email_events_queue, email_retry_queue, email_dlq
echo  Pool    : solo  (Windows-safe, no fork)
echo  Workers : 4 concurrent tasks
echo ============================================================
echo.

cd /d "%~dp0"

REM ── PYTHONPATH: email-service root + server root (for shared/) ──
set PYTHONPATH=%~dp0;%~dp0\..\..;%PYTHONPATH%

REM ── Verify celery is importable via python -m ──
python -m celery --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] celery not importable. Run:  pip install "celery[redis]"
    pause
    exit /b 1
)

echo [INFO] Starting worker...
echo.

python -m celery -A email_queue.config.celery_config:email_celery_app worker ^
    --loglevel=info ^
    --concurrency=4 ^
    --pool=solo ^
    --queues=email_events_queue,email_retry_queue,email_dlq ^
    --max-tasks-per-child=1000 ^
    --without-gossip ^
    --without-mingle ^
    --without-heartbeat ^
    -n email_worker@%%COMPUTERNAME%%

echo.
echo [INFO] Worker stopped.
pause
