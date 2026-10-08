@echo off
cd /d "%~dp0\.."
title FrameGenius clean disk
echo This deletes .venv so you can reinstall after freeing space.
pause
if exist ".venv" rmdir /s /q ".venv"
python -m pip cache purge 2>nul
echo Done. Empty Recycle Bin, then run INSTALL.bat
pause
