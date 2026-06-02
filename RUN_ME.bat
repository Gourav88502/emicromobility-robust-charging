@echo off
REM ==========================================================================
REM  Robust e-Micromobility Charging Station  -  ONE-CLICK RUN
REM  Just double-click this file. No coding needed.
REM ==========================================================================
cd /d "%~dp0"
title Robust e-Micromobility Charging - Running...
color 0A

echo(
echo ============================================================
echo   ROBUST e-MICROMOBILITY CHARGING STATION
echo   One-click run - sit back, this takes about a minute
echo ============================================================
echo(

REM --- Find Python -----------------------------------------------------------
set PY=python
%PY% --version >nul 2>&1
if errorlevel 1 set PY=py
%PY% --version >nul 2>&1
if errorlevel 1 (
  echo [X] Python was not found on this computer.
  echo     Please install Python 3.10+ from https://www.python.org/downloads/
  echo     IMPORTANT: tick "Add Python to PATH" during install, then re-run this file.
  echo(
  pause
  exit /b
)

echo [1/3] Installing the required packages ^(first time only, ~1-2 min^)...
%PY% -m pip install --quiet --disable-pip-version-check numpy scipy pandas matplotlib plotly numba openpyxl requests pvlib kaleido python-docx python-pptx odfpy pytest
echo      ...done.
echo(

echo [2/3] Running the full analysis ^(building all the charts^)...
%PY% run_analysis.py
echo(

echo [3/3] Opening the results report in your web browser...
start "" "outputs\index.html"
echo(
echo ============================================================
echo   FINISHED!  A browser tab with charts should have opened.
echo   All results are in the  "outputs"  folder.
echo ============================================================
echo(
pause
