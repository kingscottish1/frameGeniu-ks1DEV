@echo off
cd /d "%~dp0.."
title FrameGenius janitor
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "from app.services.janitor import sweep; print(sweep())"
) else (
  python -c "from app.services.janitor import sweep; print(sweep())"
)
echo Old task scratch wiped. Videos and TODAY kept.
if /I not "%~1"=="/silent" pause
