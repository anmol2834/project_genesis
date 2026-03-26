@echo off
echo Starting research-service on port 8010...
cd /d %~dp0
set PYTHONPATH=%~dp0\..\..
python main.py
