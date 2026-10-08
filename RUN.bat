@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title FrameGenius studio

if exist ".venv\Scripts\python.exe" goto have_py
echo  Installing first...
if exist "%~dp0INSTALL.cmd" (
  call "%~dp0INSTALL.cmd" /silent
) else (
  call "%~dp0INSTALL.bat" /silent
)
if errorlevel 1 (
  echo  Install failed. Free disk space, delete .venv, run INSTALL.cmd
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
echo  Opening http://127.0.0.1:8080
echo  No login. Generate is the home screen.
echo.
start "" cmd /c timeout /t 2 /nobreak ^>nul ^& start http://127.0.0.1:8080
"%VENV_PY%" "main.py" --host 0.0.0.0 --port 8080
if errorlevel 1 (
  echo  Studio exited.
  pause
)
endlocal
