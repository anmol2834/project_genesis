@echo off
echo Starting leads-service on port 8007...
cd /d %~dp0
set PYTHONPATH=%~dp0\..\..
python main.py
