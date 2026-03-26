@echo off
echo Starting email-service on port 8004...
cd /d %~dp0
set PYTHONPATH=%~dp0\..\..
python main.py
