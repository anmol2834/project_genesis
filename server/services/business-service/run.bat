@echo off
echo Starting business-service on port 8003...
cd /d %~dp0
set PYTHONPATH=%~dp0\..\..
python main.py
