@echo off
echo ================================================================================
echo   STOPPING CORE MICROSERVICES (PORTS: 8000, 8001, 8002, 8004, 8005, 8009)
echo ================================================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-NetTCPConnection -LocalPort 8000,8001,8002,8004,8005,8009 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Write-Host \"[*] Killing process PID $_...\"; Stop-Process -Id $_ -Force }"

echo.
echo ================================================================================
echo   ALL CORE SERVICES STOPPED CLEANLY
echo ================================================================================
echo.
timeout /t 2 >nul
