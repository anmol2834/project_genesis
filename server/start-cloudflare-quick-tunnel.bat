@echo off
echo ================================================================================
echo STARTING CLOUDFLARE QUICK TUNNEL (HTTPS) FOR EMAIL SERVICE (PORT 8004)
echo ================================================================================
echo.
echo Starting tunnel to http://127.0.0.1:8004...
echo Look for the 'https://*.trycloudflare.com' URL below.
echo.
"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://127.0.0.1:8004
pause
