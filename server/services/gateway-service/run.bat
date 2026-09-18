@echo off
echo Starting gateway-service on port 8000...
cd /d %~dp0
set PATH=C:\Users\anmol\AppData\Local\Python\bin;C:\Users\anmol\AppData\Local\Python\pythoncore-3.14-64;C:\Users\anmol\AppData\Local\Python\pythoncore-3.14-64\Scripts;%PATH%
set PYTHONPATH=%~dp0\..\..;%PYTHONPATH%
python main.py
