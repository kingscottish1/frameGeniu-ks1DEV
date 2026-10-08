@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
title FrameGenius Docker + Cloudflare
where docker >nul 2>&1
if errorlevel 1 (
  echo Docker Desktop is not installed.
  pause
  exit /b 1
)
echo.
echo  Studio + Cloudflare tunnel. Watch logs for trycloudflare.com
echo.
docker compose --profile tunnel up --build
if errorlevel 1 pause
endlocal
