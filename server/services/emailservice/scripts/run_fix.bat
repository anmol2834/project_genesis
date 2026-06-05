@echo off
echo ========================================
echo Email Service Account State Fix
echo ========================================
echo.
echo This script will:
echo 1. Update the database to set account_state = 'active'
echo 2. Clear all cache layers
echo 3. Verify the fix
echo.
echo Press Ctrl+C to cancel, or
pause

cd /d "%~dp0.."
python scripts\fix_account_state.py

echo.
echo ========================================
echo Fix complete!
echo ========================================
echo.
echo Next steps:
echo 1. Restart the emailservice: python main.py
echo 2. Send a test email to verify processing
echo.
pause
