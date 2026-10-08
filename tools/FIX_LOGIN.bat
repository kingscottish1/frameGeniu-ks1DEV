@echo off
cd /d "%~dp0\.."
title FrameGenius — set account
if not exist ".venv\Scripts\python.exe" (
  echo  Run GO.bat from the FrameGenius folder first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" "scripts\set_login.py"
echo.
echo  Account:  admin  /  FrameGenius!
echo  See ACCOUNT.txt
pause
