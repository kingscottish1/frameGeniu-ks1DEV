@echo off
cd /d "%~dp0\.."
title FrameGenius — reset vault
echo  This clears the encrypted database. Videos in outputs\ stay.
pause
if not exist "data" mkdir "data"
if exist "data\framegenius.db.enc" move /Y "data\framegenius.db.enc" "data\framegenius.db.enc.old" >nul
del /Q "data\.runtime.db" "data\.runtime.db-wal" "data\.runtime.db-shm" 2>nul
echo  Done. Double-click GO.bat
pause
