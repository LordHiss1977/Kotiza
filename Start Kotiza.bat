@echo off
rem Double-click to start Kotiza. Keep this window open while you work; close it to stop.
cd /d "%~dp0"
title Kotiza
where py >nul 2>nul && (py -m kotiza --open) || (python -m kotiza --open)
if errorlevel 1 (
  echo.
  echo Kotiza could not start. Is Python installed with "Add python.exe to PATH" ticked?
  pause
)
