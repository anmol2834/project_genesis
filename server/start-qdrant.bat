@echo off
REM ============================================================================
REM Start Qdrant Vector Database (Simplified)
REM ============================================================================

echo.
echo ============================================================================
echo   STARTING QDRANT VECTOR DATABASE
echo ============================================================================
echo.

REM Check if Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Docker is not running. Please start Docker Desktop first.
    pause
    exit /b 1
)

echo [OK] Docker is running

REM Remove existing container if any (ignore errors)
echo [*] Cleaning up old container...
docker stop qdrant >nul 2>&1
docker rm qdrant >nul 2>&1

REM Create new container
echo [*] Creating Qdrant container...
docker run -d --name qdrant -p 6333:6333 -p 6334:6334 -v qdrant_storage:/qdrant/storage qdrant/qdrant

if %errorlevel% neq 0 (
    echo [!] Failed to create container
    pause
    exit /b 1
)

echo [OK] Container created

REM Wait for startup
echo [*] Waiting for Qdrant to start...
ping -n 6 127.0.0.1 >nul

REM Verify it's running
docker ps --filter "name=qdrant" --format "{{.Status}}" | findstr "Up" >nul 2>&1
if %errorlevel% equ 0 (
    echo.
    echo ============================================================================
    echo   QDRANT STARTED SUCCESSFULLY
    echo ============================================================================
    echo.
    echo   REST API:  http://localhost:6333
    echo   gRPC API:  http://localhost:6334
    echo   Dashboard: http://localhost:6333/dashboard
    echo.
    echo   To stop: docker stop qdrant
    echo   To view logs: docker logs qdrant
    echo.
    echo ============================================================================
) else (
    echo [!] Container not running. Checking logs...
    docker logs qdrant
)

echo.
pause
