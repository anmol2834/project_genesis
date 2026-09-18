@echo off
echo ================================================================================
echo STARTING CLOUDFLARE QUICK TUNNEL (HTTPS) FOR EMAIL SERVICE (PORT 8004)
echo ================================================================================
echo.
echo Starting tunnel to http://127.0.0.1:8004...
echo Look for the 'https://*.trycloudflare.com' URL below.
echo.
SET CLOUDFLARED_CMD=

where cloudflared >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "CLOUDFLARED_CMD=cloudflared"
) else if exist "C:\Program Files\cloudflared\cloudflared.exe" (
    set "CLOUDFLARED_CMD=C:\Program Files\cloudflared\cloudflared.exe"
) else if exist "C:\Program Files (x86)\cloudflared\cloudflared.exe" (
    set "CLOUDFLARED_CMD=C:\Program Files (x86)\cloudflared\cloudflared.exe"
)

if "%CLOUDFLARED_CMD%"=="" (
    echo [ERROR] 'cloudflared' executable was not found on your system!
    echo.
    echo Please install Cloudflare Tunnel using winget by running:
    echo     winget install --id Cloudflare.cloudflared -e
    echo.
    echo Or download the Windows executable/installer manually from:
    echo     https://github.com/cloudflare/cloudflared/releases/latest
    echo.
    pause
    exit /b 1
)

"%CLOUDFLARED_CMD%" tunnel --url http://127.0.0.1:8004
pause
