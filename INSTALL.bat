@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title FrameGenius install
set SILENT=0
if /I "%~1"=="/silent" set SILENT=1

echo.
echo  FrameGenius install
echo  Slim package list so it fits on disk.
echo.

set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY (
  echo  ERROR: Python not found. Install Python 3.12 from python.org
  echo  Tick ADD PYTHON TO PATH then run this again.
  if "%SILENT%"=="0" pause
  exit /b 1
)

echo  [1] Python
%PY% --version || exit /b 1

echo  [2] venv
if exist ".venv\Scripts\python.exe" goto venv_ok
%PY% -m venv .venv
if errorlevel 1 (
  echo  ERROR: venv failed. Delete .venv if it is half-created.
  if "%SILENT%"=="0" pause
  exit /b 1
)
:venv_ok
set "VENV_PY=%cd%\.venv\Scripts\python.exe"

echo  [3] pip packages
"%VENV_PY%" -m pip install --upgrade pip
"%VENV_PY%" -m pip cache purge >nul 2>&1
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo  ERROR: pip failed. Usually DISK FULL.
  echo  1. Delete the .venv folder in this directory
  echo  2. Empty Recycle Bin
  echo  3. Free a few GB
  echo  4. Run INSTALL.bat again
  if "%SILENT%"=="0" pause
  exit /b 1
)

"%VENV_PY%" -c "import fastapi,uvicorn,edge_tts,imageio_ffmpeg,cryptography"
if errorlevel 1 (
  echo  ERROR: packages did not import. Disk may still be full.
  if "%SILENT%"=="0" pause
  exit /b 1
)

echo  [4] optional speech (Upload bleeps)
"%VENV_PY%" -m pip install vosk
if errorlevel 1 echo  (vosk skipped — Upload still works, swears will not bleep)
"%VENV_PY%" -m pip install faster-whisper
if errorlevel 1 echo  (faster-whisper skipped — Python 3.14 often has no wheel)

echo  [5] config
if exist "config.toml" goto env_ok
copy /Y "config.example.toml" "config.toml" >nul
:env_ok
if exist ".env" goto boot
copy /Y ".env.example" ".env" >nul
:boot

echo  [6] vault
"%VENV_PY%" "scripts\bootstrap_env.py"
if errorlevel 1 (
  echo  ERROR: bootstrap failed
  if "%SILENT%"=="0" pause
  exit /b 1
)

if not exist "outputs\videos" mkdir "outputs\videos"
if not exist "data" mkdir "data"

echo.
echo  Install OK. Next: RUN.bat or GO.bat
echo  Studio: http://127.0.0.1:8080
echo  Login gate is OFF.
echo  Bleeps: vosk in .venv. YouTube: Settings then Connect.
echo.
if "%SILENT%"=="0" pause
exit /b 0
