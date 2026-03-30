@echo off
cd /d "%~dp0"

set PYTHONPATH=%~dp0;%~dp0\..\..;%PYTHONPATH%

echo Starting Email Service (FastAPI)...
start "Email Service - FastAPI" cmd /k "set PYTHONPATH=%PYTHONPATH% && python main.py"

timeout /t 3 /nobreak >nul

echo Starting Email Service (Celery Worker)...
start "Email Service - Celery Worker" cmd /k "set PYTHONPATH=%PYTHONPATH% && python -m celery -A email_queue.config.celery_config:email_celery_app worker --loglevel=warning --concurrency=4 --pool=solo --queues=email_events_queue,email_retry_queue,email_dlq --max-tasks-per-child=1000 --without-gossip --without-mingle -n email_worker@%%COMPUTERNAME%%"

timeout /t 2 /nobreak >nul

echo Starting Email Service (Celery Beat)...
start "Email Service - Celery Beat" cmd /k "set PYTHONPATH=%PYTHONPATH% && python -m celery -A email_queue.config.celery_config:email_celery_app beat --loglevel=info"

echo.
echo All 3 processes started in separate windows:
echo   1. FastAPI server    (port 8004)
echo   2. Celery worker     (processes email events)
echo   3. Celery beat       (subscription refresh + history sync + cleanup)
