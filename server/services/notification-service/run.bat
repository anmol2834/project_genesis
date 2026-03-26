@echo off
echo Starting notification-service on port 8011...
cd /d %~dp0
set PYTHONPATH=%~dp0\..\..
python main.py
