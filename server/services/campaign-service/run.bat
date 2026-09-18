@echo off
echo Starting campaign-service on port 8006...
cd /d %~dp0
set PATH=C:\Users\anmol\AppData\Local\Python\bin;C:\Users\anmol\AppData\Local\Python\pythoncore-3.14-64;C:\Users\anmol\AppData\Local\Python\pythoncore-3.14-64\Scripts;%PATH%
set PYTHONPATH=%~dp0\..\..;%PYTHONPATH%
python main.py
