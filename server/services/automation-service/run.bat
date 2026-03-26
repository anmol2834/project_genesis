@echo off
echo Starting automation-service on port 8009...
cd /d %~dp0
set PYTHONPATH=%~dp0\..\..
python main.py
