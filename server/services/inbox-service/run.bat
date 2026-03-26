@echo off
echo Starting inbox-service on port 8005...
cd /d %~dp0
set PYTHONPATH=%~dp0\..\..
python main.py
