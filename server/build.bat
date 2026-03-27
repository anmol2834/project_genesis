@echo off
REM ============================================================================
REM build.bat — Full build + start for Project Genesis
REM
REM MUST run this before "docker compose up" on a fresh machine.
REM After first run, "docker compose up" alone is sufficient (uses cached layers).
REM
REM Usage:
REM   build.bat              First-time build + start everything
REM   build.bat --no-cache   Force full rebuild from scratch
REM   build.bat base         Rebuild base images only
REM   build.bat up           Start containers (assumes images already built)
REM ============================================================================

setlocal
set NO_CACHE=
if "%1"=="--no-cache" (
    set NO_CACHE=--no-cache
    shift
)
set MODE=%1
if "%MODE%"=="" set MODE=all

if "%MODE%"=="up"       goto :compose_up
if "%MODE%"=="base"     goto :build_base
if "%MODE%"=="all"      goto :build_all
goto :build_all

:build_base
echo.
echo [1/2] Building base image (project-genesis-base)...
docker build %NO_CACHE% -f docker/Dockerfile.base -t project-genesis-base:latest .
if errorlevel 1 ( echo FAILED: base image && exit /b 1 )

echo.
echo [2/2] Building ML base image (project-genesis-base-ml)...
docker build %NO_CACHE% -f docker/Dockerfile.base-ml -t project-genesis-base-ml:latest .
if errorlevel 1 ( echo FAILED: base-ml image && exit /b 1 )

echo.
echo Base images ready.
goto :eof

:build_all
call :build_base
if errorlevel 1 exit /b 1

echo.
echo [3/3] Building all service images + starting containers...
docker compose up --build -d
if errorlevel 1 ( echo FAILED: docker compose up && exit /b 1 )

echo.
echo All services started. Run "docker compose logs -f" to follow logs.
goto :eof

:compose_up
echo.
echo Starting containers (using cached images)...
docker compose up -d
goto :eof
