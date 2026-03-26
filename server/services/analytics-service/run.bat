@echo off
echo Starting analytics-service on port 8008...
cd /d %~dp0
set PYTHONPATH=%~dp0\..\..
python main.py
