@echo off
setlocal enabledelayedexpansion

echo ================================================================================
echo   STOPPING CORE SERVICES AND CLOSING ALL TERMINALS
echo ================================================================================
echo.

echo [1/3] Closing service terminal windows by title...
taskkill /F /FI "WINDOWTITLE eq Gateway Service [8000]*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Auth Service [8001]*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq User Service [8002]*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Email Service [8004]*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Inbox Service [8005]*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Automation Service [8009]*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Cloudflare*" >nul 2>&1

echo [2/3] Terminating any remaining processes on core ports (8000, 8001, 8002, 8004, 8005, 8009)...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ports = @(8000, 8001, 8002, 8004, 8005, 8009);" ^
    "foreach ($p in $ports) {" ^
    "    $conns = Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue;" ^
    "    foreach ($c in $conns) {" ^
    "        $pidToKill = $c.OwningProcess;" ^
    "        if ($pidToKill -gt 0) {" ^
    "            try {" ^
    "                $parentPid = (Get-CimInstance Win32_Process -Filter \"ProcessId = $pidToKill\" -ErrorAction SilentlyContinue).ParentProcessId;" ^
    "                if ($parentPid -gt 0) {" ^
    "                    $parentProc = Get-Process -Id $parentPid -ErrorAction SilentlyContinue;" ^
    "                    if ($parentProc -and $parentProc.ProcessName -in @('cmd', 'powershell', 'pwsh', 'bash', 'conhost', 'WindowsTerminal')) {" ^
    "                        Stop-Process -Id $parentPid -Force -ErrorAction SilentlyContinue;" ^
    "                    }" ^
    "                }" ^
    "            } catch {};" ^
    "            Stop-Process -Id $pidToKill -Force -ErrorAction SilentlyContinue;" ^
    "            Write-Host \"  [*] Stopped process PID $pidToKill on port $p\";" ^
    "        }" ^
    "    }" ^
    "}"

echo [3/3] Stopping Cloudflare tunnel (cloudflared)...
taskkill /F /IM cloudflared.exe >nul 2>&1

echo.
echo ================================================================================
echo   ALL 6 CORE SERVICES AND TERMINAL WINDOWS CLOSED CLEANLY
echo ================================================================================
echo.
pause
