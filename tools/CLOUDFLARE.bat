@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
title FrameGenius Cloudflare tunnel
set "CF=%cd%\tools\cloudflared.exe"

if exist "%CF%" goto have
echo Downloading cloudflared (one time)...
curl -L --retry 3 -o "%CF%" "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
if errorlevel 1 (
  echo Download failed. Install cloudflared from Cloudflare and try again.
  pause
  exit /b 1
)
:have

echo.
echo  Quick tunnel to http://127.0.0.1:8080
echo  Studio must already be running (GO.bat).
echo  Copy the https://xxxx.trycloudflare.com link when it appears.
echo  Leave this window open.
echo.
"%CF%" tunnel --no-autoupdate --url http://127.0.0.1:8080
if errorlevel 1 pause
endlocal
