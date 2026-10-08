@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
title FrameGenius shortcut

set "TARGET=%cd%\APP.cmd"
set "WORKDIR=%cd%"
set "ICON=%cd%\resource\icons\app.ico"
if not exist "%ICON%" set "ICON=%cd%\resource\icons\logo.png"
set "DEST=%USERPROFILE%\Desktop\FrameGenius.lnk"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s = (New-Object -COM WScript.Shell).CreateShortcut('%DEST%');" ^
  "$s.TargetPath = '%TARGET%';" ^
  "$s.WorkingDirectory = '%WORKDIR%';" ^
  "$s.WindowStyle = 1;" ^
  "$s.Description = 'FrameGenius · Crown AI';" ^
  "if (Test-Path '%ICON%') { $s.IconLocation = '%ICON%' };" ^
  "$s.Save()"

if exist "%DEST%" (
  echo.
  echo  Shortcut ready on your Desktop: FrameGenius
  echo  Double-click that — it is the app.
  echo.
) else (
  echo  Could not create the shortcut. Double-click APP.cmd instead.
)
if /I not "%~1"=="/silent" pause
endlocal
