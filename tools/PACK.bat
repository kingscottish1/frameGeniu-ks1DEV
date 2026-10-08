@echo off
cd /d "%~dp0\.."
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\pack_release.py
) else (
  python scripts\pack_release.py
)
echo  Zip is on the Desktop parent folder / dist\
pause
