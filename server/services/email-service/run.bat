@echo off
echo Starting email-service on port 8004...
cd /d "%~dp0"

REM ── PYTHONPATH: email-service root + server root (for shared/) ──
set PYTHONPATH=%~dp0;%~dp0\..\..;%PYTHONPATH%

python main.py
pause
