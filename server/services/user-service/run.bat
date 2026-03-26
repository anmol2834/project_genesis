@echo off
echo Starting user-service on port 8002...
cd /d %~dp0
set PYTHONPATH=%~dp0\..\..
python main.py
