@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
title FrameGenius Docker
where docker >nul 2>&1
if errorlevel 1 (
  echo Docker Desktop is not installed or not on PATH.
  echo Install it from https://www.docker.com/products/docker-desktop/
  pause
  exit /b 1
)
echo.
echo  Building and starting FrameGenius on http://127.0.0.1:8080
echo  Ctrl+C stops the containers.
echo.
docker compose up --build
if errorlevel 1 pause
endlocal
