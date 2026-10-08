@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title FrameGenius

if exist ".venv\Scripts\python.exe" goto have_py
echo  Installing first...
if exist "%~dp0INSTALL.cmd" (
  call "%~dp0INSTALL.cmd" /silent
) else (
  call "%~dp0INSTALL.bat" /silent
)
if errorlevel 1 (
  echo  Install failed. Free disk, delete .venv, run INSTALL.cmd
  pause
  exit /b 1
)
:have_py
set "VENV_PY=%cd%\.venv\Scripts\python.exe"
"%VENV_PY%" -c "import fastapi" 1>nul 2>nul
if errorlevel 1 (
  echo  Packages missing. Delete .venv then run INSTALL.cmd
  pause
  exit /b 1
)

if exist "config.toml" goto have_cfg
copy /Y "config.example.toml" "config.toml" >nul
:have_cfg
if exist ".env" goto have_env
copy /Y ".env.example" ".env" >nul
:have_env

"%VENV_PY%" "scripts\bootstrap_env.py"
echo.
echo  Starting FrameGenius app window...
echo  Crown talks and paints. Films download to outputs\videos\
echo  Close the app window to stop.
echo.
"%VENV_PY%" "desktop.py"
if errorlevel 1 (
  echo  App exited.
  pause
)
endlocal
