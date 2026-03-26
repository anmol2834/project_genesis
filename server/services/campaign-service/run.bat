@echo off
echo Starting campaign-service on port 8006...
cd /d %~dp0
set PYTHONPATH=%~dp0\..\..
python main.py
