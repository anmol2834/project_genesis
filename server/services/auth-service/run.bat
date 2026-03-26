@echo off
echo Starting auth-service on port 8001...
cd /d %~dp0
set PYTHONPATH=%~dp0\..\..
python main.py
