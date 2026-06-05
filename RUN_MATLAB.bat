@echo off
REM ==========================================================================
REM  MATLAB / Simulink study  -  ONE-CLICK RUN
REM  Runs the 4-part MATLAB/Simulink study and saves figures to outputs\matlab.
REM  Requires MATLAB + Optimization Toolbox + Simulink installed.
REM ==========================================================================
cd /d "%~dp0"
title MATLAB/Simulink study - Running...
color 0B

echo(
echo ============================================================
echo   MATLAB / SIMULINK STUDY (fleet load, smart-charging LP,
echo   solar+battery EMS, Simulink digital twin)
echo ============================================================
echo(

REM --- Find matlab.exe -------------------------------------------------------
set "MLEXE="
for /f "delims=" %%G in ('where matlab 2^>nul') do set "MLEXE=%%G"
if not defined MLEXE (
  for /d %%D in ("C:\Program Files\MATLAB\R20*") do set "MLEXE=%%D\bin\matlab.exe"
)
if not defined MLEXE (
  echo [X] MATLAB was not found. Install MATLAB ^(with Optimization Toolbox + Simulink^)
  echo     or run from the MATLAB app:  cd matlab ; run_matlab_study
  echo(
  pause
  exit /b
)

echo Using MATLAB: %MLEXE%
echo Running the study ^(MATLAB takes ~1 minute to start^)...
echo(
"%MLEXE%" -batch "cd('matlab'); run_matlab_study"
echo(
echo ============================================================
echo   FINISHED!  Figures are in:  outputs\matlab\
echo ============================================================
start "" "outputs\matlab"
echo(
pause
