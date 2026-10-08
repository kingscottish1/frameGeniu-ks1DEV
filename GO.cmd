@echo off
cd /d "%~dp0"
title FrameGenius
if exist ".venv\Scripts\python.exe" goto tryrun
echo Installing...
if exist "%~dp0INSTALL.cmd" (
  call "%~dp0INSTALL.cmd" /silent
) else (
  call "%~dp0INSTALL.bat" /silent
)
if errorlevel 1 (
  echo Install failed. Free disk, delete the .venv folder, run INSTALL.cmd
  pause
  exit /b 1
)
:tryrun
".venv\Scripts\python.exe" -c "import fastapi" 1>nul 2>nul
if errorlevel 1 (
  echo Packages incomplete. Delete .venv then run INSTALL.cmd
  pause
  exit /b 1
)
if exist "%~dp0RUN.cmd" (
  call "%~dp0RUN.cmd"
) else (
  call "%~dp0RUN.bat"
)
