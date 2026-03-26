@echo off
echo ================================================================================
echo STARTING ALL MICROSERVICES
echo ================================================================================
echo.

REM Check if .env exists
if not exist .env (
    echo ERROR: .env file not found
    echo Please ensure .env file exists in the server directory
    exit /b 1
)

echo Installing global dependencies...
pip install -r requirements.txt
echo.

echo ================================================================================
echo STARTING SERVICES
echo ================================================================================
echo.

REM Create logs directory if it doesn't exist
if not exist logs mkdir logs

REM Start each service in a new window
echo Starting Gateway Service (Port 8000)...
start "Gateway Service" cmd /k "cd services\gateway-service && run.bat"
timeout /t 2 /nobreak >nul

echo Starting Auth Service (Port 8001)...
start "Auth Service" cmd /k "cd services\auth-service && run.bat"
timeout /t 2 /nobreak >nul

echo Starting User Service (Port 8002)...
start "User Service" cmd /k "cd services\user-service && run.bat"
timeout /t 2 /nobreak >nul

echo Starting Business Service (Port 8003)...
start "Business Service" cmd /k "cd services\business-service && run.bat"
timeout /t 2 /nobreak >nul

echo Starting Email Service (Port 8004)...
start "Email Service" cmd /k "cd services\email-service && run.bat"
timeout /t 2 /nobreak >nul

echo Starting Inbox Service (Port 8005)...
start "Inbox Service" cmd /k "cd services\inbox-service && run.bat"
timeout /t 2 /nobreak >nul

echo Starting Campaign Service (Port 8006)...
start "Campaign Service" cmd /k "cd services\campaign-service && run.bat"
timeout /t 2 /nobreak >nul

echo Starting Leads Service (Port 8007)...
start "Leads Service" cmd /k "cd services\leads-service && run.bat"
timeout /t 2 /nobreak >nul

echo Starting Analytics Service (Port 8008)...
start "Analytics Service" cmd /k "cd services\analytics-service && run.bat"
timeout /t 2 /nobreak >nul

echo Starting Automation Service (Port 8009)...
start "Automation Service" cmd /k "cd services\automation-service && run.bat"
timeout /t 2 /nobreak >nul

echo Starting Research Service (Port 8010)...
start "Research Service" cmd /k "cd services\research-service && run.bat"
timeout /t 2 /nobreak >nul

echo Starting Notification Service (Port 8011)...
start "Notification Service" cmd /k "cd services\notification-service && run.bat"
timeout /t 2 /nobreak >nul

echo.
echo ================================================================================
echo ALL SERVICES STARTED!
echo ================================================================================
echo.
echo Service URLs:
echo   Gateway:      http://localhost:8000/health
echo   Auth:         http://localhost:8001/health
echo   User:         http://localhost:8002/health
echo   Business:     http://localhost:8003/health
echo   Email:        http://localhost:8004/health
echo   Inbox:        http://localhost:8005/health
echo   Campaign:     http://localhost:8006/health
echo   Leads:        http://localhost:8007/health
echo   Analytics:    http://localhost:8008/health
echo   Automation:   http://localhost:8009/health
echo   Research:     http://localhost:8010/health
echo   Notification: http://localhost:8011/health
echo.
echo Press any key to exit...
pause >nul
