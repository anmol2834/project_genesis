@echo off
echo ========================================
echo Automation Service - Celery Beat
echo ========================================
echo Schedules: learning cycle (6h), expire pending (2h),
echo            push cache (6h), cleanup logs (daily 02:00)
echo ========================================

cd /d "%~dp0"
python -m celery -A celery_worker beat --loglevel=info

pause
