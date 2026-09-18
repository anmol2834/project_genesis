@echo off
setlocal enabledelayedexpansion

echo ================================================================================
echo   STARTING CORE MICROSERVICES (PROJECT GENESIS)
echo ================================================================================
echo.

REM Move to server directory
cd /d "%~dp0"

REM 1. Check if .env exists
if not exist ".env" (
    echo [ERROR] .env file not found in: %cd%
    echo Please ensure the .env file is present before launching services.
    pause
    exit /b 1
)

REM 2. Activate Python Virtual Environment
if exist "%~dp0venv\Scripts\activate.bat" (
    echo [OK] Activating virtual environment: %~dp0venv
    call "%~dp0venv\Scripts\activate.bat"
) else (
    echo [WARNING] venv not found at %~dp0venv. Falling back to system Python.
)

REM Set root PYTHONPATH
set PYTHONPATH=%~dp0;%PYTHONPATH%

REM Create logs directory if it doesn't exist
if not exist "logs" mkdir logs

echo.
echo ================================================================================
echo   LAUNCHING 6 CORE SERVICES
echo ================================================================================
echo.

REM 1. Gateway Service (Port 8000)
echo [1/6] Starting Gateway Service (Port 8000)...
start "Gateway Service [8000]" cmd /k "cd /d %~dp0services\gateway-service && set PYTHONPATH=%~dp0;%~dp0services\gateway-service && %~dp0venv\Scripts\python.exe main.py"
ping 127.0.0.1 -n 2 >nul

REM 2. Auth Service (Port 8001)
echo [2/6] Starting Auth Service (Port 8001)...
start "Auth Service [8001]" cmd /k "cd /d %~dp0services\auth-service && set PYTHONPATH=%~dp0;%~dp0services\auth-service && %~dp0venv\Scripts\python.exe main.py"
ping 127.0.0.1 -n 2 >nul

REM 3. User Service (Port 8002)
echo [3/6] Starting User Service (Port 8002)...
start "User Service [8002]" cmd /k "cd /d %~dp0services\user-service && set PYTHONPATH=%~dp0;%~dp0services\user-service && %~dp0venv\Scripts\python.exe main.py"
ping 127.0.0.1 -n 2 >nul

REM 4. Email Service (Port 8004)
echo [4/6] Starting Email Service (Port 8004)...
start "Email Service [8004]" cmd /k "cd /d %~dp0services\emailservice && set PYTHONPATH=%~dp0;%~dp0services\emailservice && %~dp0venv\Scripts\python.exe main.py"
ping 127.0.0.1 -n 2 >nul

REM 5. Inbox Service (Port 8005)
echo [5/6] Starting Inbox Service (Port 8005)...
start "Inbox Service [8005]" cmd /k "cd /d %~dp0services\inbox-service && set PYTHONPATH=%~dp0;%~dp0services\inbox-service && %~dp0venv\Scripts\python.exe main.py"
ping 127.0.0.1 -n 2 >nul

REM 6. Automation Service (Port 8009)
echo [6/6] Starting Automation Service (Port 8009)...
start "Automation Service [8009]" cmd /k "cd /d %~dp0services\automationservice && set PYTHONPATH=%~dp0;%~dp0services\automationservice && %~dp0venv\Scripts\python.exe main.py"
ping 127.0.0.1 -n 2 >nul

echo.
echo ================================================================================
echo   ALL 6 CORE SERVICES LAUNCHED SUCCESSFULLY
echo ================================================================================
echo.
echo   Service Endpoints:
echo   - Gateway Service:    http://localhost:8000/health
echo   - Auth Service:       http://localhost:8001/health
echo   - User Service:       http://localhost:8002/health
echo   - Email Service:      http://localhost:8004/health
echo   - Inbox Service:      http://localhost:8005/health
echo   - Automation Service: http://localhost:8009/health
echo.
echo   API Gateway Swagger Docs:
echo   - Gateway:    http://localhost:8000/docs
echo   - Automation: http://localhost:8009/docs
echo   - Email:      http://localhost:8004/docs
echo.
echo ================================================================================
echo   To stop all services cleanly, run: stop-core-services.bat
echo ================================================================================
echo.
ping 127.0.0.1 -n 3 >nul
