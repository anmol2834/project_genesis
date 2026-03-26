@echo off
echo Starting gateway-service on port 8000...
cd /d %~dp0
set PYTHONPATH=%~dp0\..\..
python main.py
